#!/usr/bin/env python3
"""
arq-pkg-manager — graphical package manager for ArqOS (arq-repo repository)
Requires: python-gobject, gtk4, polkit
"""
import gi, subprocess, threading
gi.require_version("Gtk","4.0")
from gi.repository import Gtk, GLib, Pango, GdkPixbuf, Gio

REPO = "arq-repo"
# GLib requires reverse-domain format. KDE Wayland maps this to the .desktop
# file via StartupWMClass or by stripping the domain prefix — set
# StartupWMClass=arq-pkg-manager in the .desktop to ensure correct matching.
APP_ID = "org.arqos.PkgManager"
TASKBAR_ICON = "arq-pkg-manager"   # name of installed icon, matches .desktop Icon=
HEADER_ICON  = "arq-pkg-manager-logo"  # separate in-app header logo

def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), 1

def get_repo_packages():
    out, _, _ = run_cmd(["pacman", "-Slq", REPO])
    return [l.strip() for l in out.splitlines() if l.strip()]

def get_installed():
    out, _, _ = run_cmd(["pacman", "-Q"])
    installed = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2:
            installed[parts[0]] = parts[1]
    return installed

def get_updates():
    out, _, _ = run_cmd(["pacman", "-Qu"])
    updates = set()
    for line in out.splitlines():
        parts = line.split()
        if parts:
            updates.add(parts[0])
    return updates


class PkgManagerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        self.win = MainWindow(app)
        self.win.present()


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="ArqOS Package Manager")
        self.set_default_size(820, 620)
        # Window icon (taskbar, alt-tab)
        # Taskbar / window switcher icon
        self.set_icon_name(TASKBAR_ICON)
        self.selected = set()
        self.all_packages = []
        self.installed = {}
        self.updates = set()
        self.filter_mode = "all"

        self._build_ui()
        self._load_packages()

    def _build_ui(self):
        css = Gtk.CssProvider()
        css.load_from_data(b"""
        .title-label { font-size: 16px; font-weight: bold; color: #e86b1f; }
        .subtitle-label { font-size: 11px; color: alpha(currentColor, 0.5); }
        .stat-box { background: alpha(currentColor, 0.05); border-radius: 8px; padding: 8px 12px; }
        .stat-num { font-size: 20px; font-weight: bold; }
        .stat-lbl { font-size: 10px; color: alpha(currentColor, 0.5); }
        .badge-ins { background: #1a3a2a; color: #5dbf82; border-radius: 6px; padding: 2px 8px; font-size: 11px; }
        .badge-upd { background: #3a2a00; color: #f0a500; border-radius: 6px; padding: 2px 8px; font-size: 11px; }
        .badge-avl { background: alpha(currentColor, 0.05); color: alpha(currentColor, 0.4); border-radius: 6px; padding: 2px 8px; font-size: 11px; }
        .filter-btn:checked { background: #e86b1f; color: white; }
        .terminal { background: #111; color: #e0e0e0; border-radius: 8px; padding: 10px; font-family: monospace; font-size: 12px; }
        .btn-primary { background: #e86b1f; color: white; border-radius: 8px; }
        .btn-primary:hover { background: #cf5c10; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root)

        # Header
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hdr.set_margin_start(16); hdr.set_margin_end(16)
        hdr.set_margin_top(14); hdr.set_margin_bottom(14)

        # Header logo — separate from taskbar icon, falls back gracefully
        logo_img = Gtk.Image()
        logo_img.set_pixel_size(36)
        icon_theme = Gtk.IconTheme.get_for_display(self.get_display())
        if icon_theme.has_icon(HEADER_ICON):
            logo_img.set_from_icon_name(HEADER_ICON)
        elif icon_theme.has_icon(TASKBAR_ICON):
            logo_img.set_from_icon_name(TASKBAR_ICON)
        else:
            logo_img.set_from_icon_name("system-software-install")
        hdr.append(logo_img)

        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        t1 = Gtk.Label(label="ArqOS Package Manager")
        t1.add_css_class("title-label")
        t1.set_halign(Gtk.Align.START)
        t2 = Gtk.Label(label=f"repository: {REPO}")
        t2.add_css_class("subtitle-label")
        t2.set_halign(Gtk.Align.START)
        titles.append(t1); titles.append(t2)
        hdr.append(titles)

        root.append(hdr)
        root.append(Gtk.Separator())

        # Content
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_start(16); content.set_margin_end(16)
        content.set_margin_top(12); content.set_margin_bottom(12)
        root.append(content)

        # Stats
        stats_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.lbl_total = self._stat_widget(stats_row, "0", "packages in repo")
        self.lbl_ins   = self._stat_widget(stats_row, "0", "installed")
        self.lbl_upd   = self._stat_widget(stats_row, "0", "updates available")
        content.append(stats_row)

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("search packages...")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", lambda _: self._filter())
        toolbar.append(self.search)

        for label, mode in [("All","all"),("Installed","installed"),("Updates","updates"),("Available","available")]:
            btn = Gtk.ToggleButton(label=label)
            btn.add_css_class("filter-btn")
            if mode == "all": btn.set_active(True)
            btn.connect("clicked", self._on_filter_click, mode)
            toolbar.append(btn)
            setattr(self, f"fbtn_{mode}", btn)
        content.append(toolbar)

        # Package list
        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        sw.set_min_content_height(300)
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.add_css_class("boxed-list")
        sw.set_child(self.list_box)
        content.append(sw)

        # Selection label
        self.sel_lbl = Gtk.Label(label="")
        self.sel_lbl.set_halign(Gtk.Align.START)
        self.sel_lbl.add_css_class("subtitle-label")
        content.append(self.sel_lbl)

        # Buttons
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.btn_install = Gtk.Button(label="⬇ Install selected")
        self.btn_install.add_css_class("btn-primary")
        self.btn_install.set_sensitive(False)
        self.btn_install.connect("clicked", self._on_install)

        self.btn_update = Gtk.Button(label="↺ Update system")
        self.btn_update.add_css_class("btn-primary")
        self.btn_update.connect("clicked", self._on_update)

        self.btn_sync = Gtk.Button(label="☁ Sync database")
        self.btn_sync.connect("clicked", self._on_sync)

        btn_row.append(self.btn_install)
        btn_row.append(self.btn_update)
        btn_row.append(self.btn_sync)
        content.append(btn_row)

        # Terminal
        term_sw = Gtk.ScrolledWindow()
        term_sw.set_min_content_height(110)
        term_sw.set_max_content_height(110)
        self.term_buf = Gtk.TextBuffer()
        self.term_view = Gtk.TextView(buffer=self.term_buf)
        self.term_view.set_editable(False)
        self.term_view.set_monospace(True)
        self.term_view.add_css_class("terminal")
        term_sw.set_child(self.term_view)
        content.append(term_sw)

        # Spinner
        self.spinner = Gtk.Spinner()
        self.status_lbl = Gtk.Label(label="Loading package list...")
        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_row.append(self.spinner); status_row.append(self.status_lbl)
        self.status_row = status_row
        content.append(status_row)
        self.spinner.start()

    def _stat_widget(self, parent, num, lbl):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_hexpand(True)
        box.add_css_class("stat-box")
        n = Gtk.Label(label=num)
        n.add_css_class("stat-num")
        n.set_halign(Gtk.Align.START)
        l = Gtk.Label(label=lbl)
        l.add_css_class("stat-lbl")
        l.set_halign(Gtk.Align.START)
        box.append(n); box.append(l)
        parent.append(box)
        return n

    def _load_packages(self):
        def worker():
            pkgs = get_repo_packages()
            inst = get_installed()
            upds = get_updates()
            GLib.idle_add(self._on_loaded, pkgs, inst, upds)
        threading.Thread(target=worker, daemon=True).start()

    def _on_loaded(self, pkgs, inst, upds):
        self.all_packages = pkgs
        self.installed = inst
        self.updates = upds
        self.spinner.stop()
        self.status_row.set_visible(False)
        self._update_stats()
        self._filter()

    def _update_stats(self):
        ins_count = sum(1 for p in self.all_packages if p in self.installed)
        upd_count = sum(1 for p in self.all_packages if p in self.updates)
        self.lbl_total.set_label(str(len(self.all_packages)))
        self.lbl_ins.set_label(str(ins_count))
        self.lbl_upd.set_label(str(upd_count))

    def _pkg_status(self, name):
        if name not in self.installed: return "available"
        if name in self.updates: return "updates"
        return "installed"

    def _filter(self):
        q = self.search.get_text().lower()
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)
        shown = [p for p in self.all_packages
                 if q in p.lower()
                 and (self.filter_mode == "all"
                      or self._pkg_status(p) == self.filter_mode)]
        for name in shown:
            self.list_box.append(self._make_row(name))

    def _make_row(self, name):
        st = self._pkg_status(name)
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(10); box.set_margin_end(10)
        box.set_margin_top(8); box.set_margin_bottom(8)

        chk = Gtk.CheckButton()
        chk.set_active(name in self.selected)
        chk.connect("toggled", self._on_check, name)
        box.append(chk)

        nm_lbl = Gtk.Label(label=name)
        nm_lbl.set_halign(Gtk.Align.START)
        nm_lbl.set_hexpand(True)
        nm_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        attr = Pango.AttrList()
        attr.insert(Pango.attr_family_new("monospace"))
        nm_lbl.set_attributes(attr)
        box.append(nm_lbl)

        badge = Gtk.Label()
        if st == "installed":
            badge.set_label("installed")
            badge.add_css_class("badge-ins")
        elif st == "updates":
            badge.set_label("update available")
            badge.add_css_class("badge-upd")
        else:
            badge.set_label("available")
            badge.add_css_class("badge-avl")
        box.append(badge)

        row.set_child(box)
        return row

    def _on_check(self, chk, name):
        if chk.get_active(): self.selected.add(name)
        else: self.selected.discard(name)
        self.btn_install.set_sensitive(bool(self.selected))
        n = len(self.selected)
        self.sel_lbl.set_label(f"{n} selected" if n else "")

    def _on_filter_click(self, btn, mode):
        if btn.get_active():
            self.filter_mode = mode
            for m in ["all","installed","updates","available"]:
                b = getattr(self, f"fbtn_{m}")
                if m != mode: b.set_active(False)
            self._filter()
        elif self.filter_mode == mode:
            btn.set_active(True)

    def _term_print(self, text):
        end = self.term_buf.get_end_iter()
        self.term_buf.insert(end, text + "\n")
        self.term_view.scroll_to_iter(self.term_buf.get_end_iter(), 0, False, 0, 0)

    def _run_pkexec(self, args, on_done):
        def worker():
            self._term_print(f"$ sudo {' '.join(args)}")
            proc = subprocess.Popen(
                ["pkexec"] + args,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                GLib.idle_add(self._term_print, line.rstrip())
            proc.wait()
            GLib.idle_add(on_done, proc.returncode)
        threading.Thread(target=worker, daemon=True).start()

    def _on_install(self, _):
        pkgs = list(self.selected)
        self.btn_install.set_sensitive(False)
        def done(rc):
            if rc == 0:
                self._term_print("✓ Installation complete.")
                self.selected.clear()
                self._load_packages()
            else:
                self._term_print("✗ Installation failed.")
        self._run_pkexec(["pacman", "-S", "--needed", "--noconfirm"] + pkgs, done)

    def _on_update(self, _):
        def done(rc):
            if rc == 0:
                self._term_print("✓ System updated successfully.")
                self._load_packages()
            else:
                self._term_print("✗ Update failed.")
        self._run_pkexec(["pacman", "-Syu", "--noconfirm"], done)

    def _on_sync(self, _):
        def done(rc):
            if rc == 0:
                self._term_print("✓ Database synchronized.")
                self._load_packages()
            else:
                self._term_print("✗ Sync failed.")
        self._run_pkexec(["pacman", "-Sy"], done)


if __name__ == "__main__":
    import sys
    app = PkgManagerApp()
    sys.exit(app.run(sys.argv))
