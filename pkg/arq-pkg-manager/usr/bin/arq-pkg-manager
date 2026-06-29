#!/usr/bin/env python3
"""
arq-pkg-manager — graphical package manager for ArqOS (arq-repo repository)
Requires: python-gobject, gtk4, polkit
"""
import gi, subprocess, threading, os, re
gi.require_version("Gtk","4.0")
from gi.repository import Gtk, GLib, Pango, Gio

REPO = "arq-repo"
APP_ID = "org.arqos.PkgManager"
TASKBAR_ICON = "arq-pkg-manager"
HEADER_ICON  = "arq-pkg-manager-logo"

# Available kernels: (display name, pacman pkg, headers pkg, description)
KERNELS = [
    ("linux",         "linux",         "linux-headers",
     "Vanilla Linux kernel — stable, default"),
    ("linux-zen",     "linux-zen",     "linux-zen-headers",
     "Zen kernel — optimised for desktop responsiveness"),
    ("linux-lts",     "linux-lts",     "linux-lts-headers",
     "Long-Term Support kernel — maximum stability"),
    ("linux-hardened","linux-hardened","linux-hardened-headers",
     "Hardened kernel — security-focused patches"),
    ("linux-rt",      "linux-rt",      "linux-rt-headers",
     "Real-Time kernel — low-latency, pro audio"),
    ("linux-rt-lts",  "linux-rt-lts",  "linux-rt-lts-headers",
     "Real-Time LTS kernel — low-latency + stability"),
]

# ── helpers ──────────────────────────────────────────────────────────────────

def run_cmd(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
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

def detect_bootloader():
    """Return 'grub', 'refind', or 'unknown'."""
    if os.path.isdir("/boot/grub") or os.path.isfile("/boot/grub/grub.cfg"):
        return "grub"
    if os.path.isdir("/boot/EFI/refind") or os.path.isfile("/boot/refind_linux.conf"):
        return "refind"
    out, _, _ = run_cmd(["bootctl", "status"])
    if "grub" in out.lower():
        return "grub"
    return "unknown"

# ── application ──────────────────────────────────────────────────────────────

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
        self.set_default_size(860, 660)
        self.set_icon_name(TASKBAR_ICON)
        self.selected = set()
        self.all_packages = []
        self.installed = {}
        self.updates = set()
        self.filter_mode = "all"
        self._build_ui()
        self._load_packages()

    # ── CSS + skeleton ────────────────────────────────────────────────────────

    def _build_ui(self):
        css = Gtk.CssProvider()
        css.load_from_data(b"""
        .title-label  { font-size:16px; font-weight:bold; color:#e86b1f; }
        .subtitle-label { font-size:11px; color:alpha(currentColor,0.5); }
        .stat-box     { background:alpha(currentColor,0.05); border-radius:8px; padding:8px 12px; }
        .stat-num     { font-size:20px; font-weight:bold; }
        .stat-lbl     { font-size:10px; color:alpha(currentColor,0.5); }
        .badge-ins    { background:#1a3a2a; color:#5dbf82; border-radius:6px; padding:2px 8px; font-size:11px; }
        .badge-upd    { background:#3a2a00; color:#f0a500; border-radius:6px; padding:2px 8px; font-size:11px; }
        .badge-avl    { background:alpha(currentColor,0.05); color:alpha(currentColor,0.4); border-radius:6px; padding:2px 8px; font-size:11px; }
        .badge-run    { background:#0a2a3a; color:#5bc0de; border-radius:6px; padding:2px 8px; font-size:11px; }
        .filter-btn:checked { background:#e86b1f; color:white; }
        .terminal     { background:#111; color:#e0e0e0; border-radius:8px; padding:10px; font-family:monospace; font-size:12px; }
        .btn-primary  { background:#e86b1f; color:white; border-radius:8px; }
        .btn-primary:hover { background:#cf5c10; }
        .btn-danger   { background:#a83232; color:white; border-radius:8px; }
        .btn-danger:hover { background:#8a2020; }
        .kernel-card  { border-radius:10px; border:1px solid alpha(currentColor,0.12); padding:14px; }
        .kernel-name  { font-size:14px; font-weight:bold; font-family:monospace; }
        .kernel-desc  { font-size:12px; color:alpha(currentColor,0.6); }
        .section-title { font-size:13px; font-weight:bold; color:#e86b1f; }
        .info-box     { background:alpha(currentColor,0.04); border-radius:8px; padding:10px 14px; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root)

        # header
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hdr.set_margin_start(16); hdr.set_margin_end(16)
        hdr.set_margin_top(14);   hdr.set_margin_bottom(14)
        logo = Gtk.Image()
        logo.set_pixel_size(36)
        ith = Gtk.IconTheme.get_for_display(self.get_display())
        logo.set_from_icon_name(
            HEADER_ICON if ith.has_icon(HEADER_ICON)
            else TASKBAR_ICON if ith.has_icon(TASKBAR_ICON)
            else "system-software-install"
        )
        hdr.append(logo)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        t1 = Gtk.Label(label="ArqOS Package Manager"); t1.add_css_class("title-label"); t1.set_halign(Gtk.Align.START)
        t2 = Gtk.Label(label=f"repository: {REPO}");   t2.add_css_class("subtitle-label"); t2.set_halign(Gtk.Align.START)
        titles.append(t1); titles.append(t2)
        hdr.append(titles)
        root.append(hdr)
        root.append(Gtk.Separator())

        # notebook tabs
        nb = Gtk.Notebook()
        nb.set_margin_start(0); nb.set_margin_end(0)
        nb.set_vexpand(True)
        root.append(nb)

        nb.append_page(self._build_packages_tab(), Gtk.Label(label="📦  Packages"))
        nb.append_page(self._build_kernels_tab(),  Gtk.Label(label="🐧  Kernels"))

    # ── PACKAGES TAB ─────────────────────────────────────────────────────────

    def _build_packages_tab(self):
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_start(16); content.set_margin_end(16)
        content.set_margin_top(12);   content.set_margin_bottom(12)

        stats_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.lbl_total = self._stat_widget(stats_row, "0", "packages in repo")
        self.lbl_ins   = self._stat_widget(stats_row, "0", "installed")
        self.lbl_upd   = self._stat_widget(stats_row, "0", "updates available")
        content.append(stats_row)

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

        sw = Gtk.ScrolledWindow(); sw.set_vexpand(True); sw.set_min_content_height(280)
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.add_css_class("boxed-list")
        sw.set_child(self.list_box)
        content.append(sw)

        self.sel_lbl = Gtk.Label(label=""); self.sel_lbl.set_halign(Gtk.Align.START); self.sel_lbl.add_css_class("subtitle-label")
        content.append(self.sel_lbl)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.btn_install = Gtk.Button(label="⬇ Install selected"); self.btn_install.add_css_class("btn-primary"); self.btn_install.set_sensitive(False); self.btn_install.connect("clicked", self._on_install)
        self.btn_update  = Gtk.Button(label="↺ Update system");    self.btn_update.add_css_class("btn-primary");  self.btn_update.connect("clicked", self._on_update)
        self.btn_sync    = Gtk.Button(label="☁ Sync database");    self.btn_sync.connect("clicked", self._on_sync)
        btn_row.append(self.btn_install); btn_row.append(self.btn_update); btn_row.append(self.btn_sync)
        content.append(btn_row)

        content.append(self._build_terminal())

        self.spinner = Gtk.Spinner()
        self.status_lbl = Gtk.Label(label="Loading package list...")
        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_row.append(self.spinner); status_row.append(self.status_lbl)
        self.status_row = status_row
        content.append(status_row)
        self.spinner.start()

        return content

    # ── KERNELS TAB ──────────────────────────────────────────────────────────

    def _build_kernels_tab(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        sw = Gtk.ScrolledWindow(); sw.set_vexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(16); content.set_margin_end(16)
        content.set_margin_top(14);   content.set_margin_bottom(14)
        sw.set_child(content)
        outer.append(sw)

        # info box
        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        info.add_css_class("info-box")
        ico = Gtk.Image.new_from_icon_name("dialog-information-symbolic"); ico.set_pixel_size(18)
        lbl = Gtk.Label(label="Installing a kernel will also install its headers and automatically regenerate the bootloader config.")
        lbl.set_wrap(True); lbl.set_halign(Gtk.Align.START); lbl.set_hexpand(True)
        lbl.add_css_class("subtitle-label")
        info.append(ico); info.append(lbl)
        content.append(info)

        # bootloader detection row
        bl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bl_row.add_css_class("info-box")
        bl_ico = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic"); bl_ico.set_pixel_size(16)
        self.bl_lbl = Gtk.Label(label="Detecting bootloader…")
        self.bl_lbl.set_halign(Gtk.Align.START); self.bl_lbl.set_hexpand(True)
        self.bl_lbl.add_css_class("subtitle-label")
        bl_row.append(bl_ico); bl_row.append(self.bl_lbl)
        content.append(bl_row)

        # section title
        sec = Gtk.Label(label="Available kernels"); sec.add_css_class("section-title"); sec.set_halign(Gtk.Align.START)
        content.append(sec)

        # kernel cards
        self.kernel_rows = {}
        for pkg, kern_pkg, headers_pkg, desc in KERNELS:
            card, btn_inst, btn_rem = self._kernel_card(pkg, kern_pkg, headers_pkg, desc)
            self.kernel_rows[pkg] = (btn_inst, btn_rem)
            content.append(card)

        # kernel terminal
        outer.append(Gtk.Separator())
        kterm_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        kterm_box.set_margin_start(16); kterm_box.set_margin_end(16)
        kterm_box.set_margin_top(8);    kterm_box.set_margin_bottom(12)
        self.k_term_buf  = Gtk.TextBuffer()
        self.k_term_view = Gtk.TextView(buffer=self.k_term_buf)
        self.k_term_view.set_editable(False); self.k_term_view.set_monospace(True)
        self.k_term_view.add_css_class("terminal")
        k_sw = Gtk.ScrolledWindow(); k_sw.set_min_content_height(120); k_sw.set_max_content_height(120)
        k_sw.set_child(self.k_term_view)
        kterm_box.append(k_sw)
        outer.append(kterm_box)

        # detect bootloader async
        threading.Thread(target=self._detect_bl, daemon=True).start()

        return outer

    def _kernel_card(self, pkg, kern_pkg, headers_pkg, desc):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("kernel-card")

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_box.set_hexpand(True)
        name_lbl = Gtk.Label(label=kern_pkg); name_lbl.add_css_class("kernel-name"); name_lbl.set_halign(Gtk.Align.START)
        desc_lbl = Gtk.Label(label=desc);     desc_lbl.add_css_class("kernel-desc");  desc_lbl.set_halign(Gtk.Align.START)
        name_box.append(name_lbl); name_box.append(desc_lbl)
        top.append(name_box)

        btn_inst = Gtk.Button(label="⬇ Install"); btn_inst.add_css_class("btn-primary")
        btn_rem  = Gtk.Button(label="✕ Remove");  btn_rem.add_css_class("btn-danger")

        btn_inst.connect("clicked", self._on_kernel_install, kern_pkg, headers_pkg, btn_inst, btn_rem)
        btn_rem.connect( "clicked", self._on_kernel_remove,  kern_pkg, headers_pkg, btn_inst, btn_rem)

        top.append(btn_inst); top.append(btn_rem)
        card.append(top)

        # will be updated after installed dict loads
        card._kern_pkg     = kern_pkg
        card._headers_pkg  = headers_pkg
        card._btn_inst     = btn_inst
        card._btn_rem      = btn_rem

        return card, btn_inst, btn_rem

    def _detect_bl(self):
        bl = detect_bootloader()
        GLib.idle_add(self._on_bl_detected, bl)

    def _on_bl_detected(self, bl):
        labels = {
            "grub":    "Bootloader: GRUB  (grub-mkconfig will be run after kernel install)",
            "refind":  "Bootloader: rEFInd  (refind-install will update entries automatically)",
            "unknown": "Bootloader: unknown  (you may need to update it manually)",
        }
        self.bl_lbl.set_label(labels.get(bl, labels["unknown"]))
        self._bootloader = bl

    # ── shared terminal ───────────────────────────────────────────────────────

    def _build_terminal(self):
        self.term_buf  = Gtk.TextBuffer()
        self.term_view = Gtk.TextView(buffer=self.term_buf)
        self.term_view.set_editable(False); self.term_view.set_monospace(True)
        self.term_view.add_css_class("terminal")
        sw = Gtk.ScrolledWindow(); sw.set_min_content_height(110); sw.set_max_content_height(110)
        sw.set_child(self.term_view)
        return sw

    def _term_print(self, text, buf=None):
        b = buf or self.term_buf
        end = b.get_end_iter()
        b.insert(end, text + "\n")
        # scroll whichever view owns the buffer
        view = self.term_view if b is self.term_buf else self.k_term_view
        view.scroll_to_iter(b.get_end_iter(), 0, False, 0, 0)

    # ── pkexec runner ─────────────────────────────────────────────────────────

    def _run_pkexec(self, args, on_done, buf=None):
        b = buf or self.term_buf
        def worker():
            GLib.idle_add(self._term_print, f"$ sudo {' '.join(args)}", b)
            proc = subprocess.Popen(
                ["pkexec"] + args,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                GLib.idle_add(self._term_print, line.rstrip(), b)
            proc.wait()
            GLib.idle_add(on_done, proc.returncode)
        threading.Thread(target=worker, daemon=True).start()

    def _run_script(self, script, on_done, buf=None):
        """Run a multi-command shell script via pkexec bash."""
        b = buf or self.k_term_buf
        def worker():
            GLib.idle_add(self._term_print, "$ running kernel setup script…", b)
            proc = subprocess.Popen(
                ["pkexec", "bash", "-c", script],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                GLib.idle_add(self._term_print, line.rstrip(), b)
            proc.wait()
            GLib.idle_add(on_done, proc.returncode)
        threading.Thread(target=worker, daemon=True).start()

    # ── kernel actions ────────────────────────────────────────────────────────

    def _bootloader_regen_cmd(self):
        bl = getattr(self, "_bootloader", "unknown")
        if bl == "grub":
            return "grub-mkconfig -o /boot/grub/grub.cfg"
        if bl == "refind":
            return "refind-install --usedefault /dev/$(lsblk -no pkname $(findmnt -n -o SOURCE /))"
        return "echo 'Unknown bootloader — skipping bootloader update, update manually.'"

    def _on_kernel_install(self, _, kern_pkg, headers_pkg, btn_inst, btn_rem):
        btn_inst.set_sensitive(False); btn_rem.set_sensitive(False)
        bl_cmd = self._bootloader_regen_cmd()
        script = (
            f"pacman -S --needed --noconfirm {kern_pkg} {headers_pkg} && "
            f"mkinitcpio -P && "
            f"{bl_cmd}"
        )
        def done(rc):
            btn_inst.set_sensitive(True); btn_rem.set_sensitive(True)
            if rc == 0:
                self._term_print(f"✓ {kern_pkg} installed and bootloader updated.", self.k_term_buf)
                self._refresh_kernel_buttons()
            else:
                self._term_print(f"✗ Failed to install {kern_pkg}.", self.k_term_buf)
        self._run_script(script, done, self.k_term_buf)

    def _on_kernel_remove(self, _, kern_pkg, headers_pkg, btn_inst, btn_rem):
        # safety: don't remove the running kernel
        running_out, _, _ = run_cmd(["uname", "-r"])
        if kern_pkg in running_out:
            self._term_print(f"✗ Cannot remove {kern_pkg} — it is the currently running kernel.", self.k_term_buf)
            return

        btn_inst.set_sensitive(False); btn_rem.set_sensitive(False)
        bl_cmd = self._bootloader_regen_cmd()
        script = (
            f"pacman -R --noconfirm {kern_pkg} {headers_pkg} ; "
            f"{bl_cmd}"
        )
        def done(rc):
            btn_inst.set_sensitive(True); btn_rem.set_sensitive(True)
            if rc == 0:
                self._term_print(f"✓ {kern_pkg} removed and bootloader updated.", self.k_term_buf)
                self._refresh_kernel_buttons()
            else:
                self._term_print(f"✗ Failed to remove {kern_pkg}.", self.k_term_buf)
        self._run_script(script, done, self.k_term_buf)

    def _refresh_kernel_buttons(self):
        def worker():
            inst = get_installed()
            running_out, _, _ = run_cmd(["uname", "-r"])
            GLib.idle_add(self._apply_kernel_button_states, inst, running_out)
        threading.Thread(target=worker, daemon=True).start()

    def _apply_kernel_button_states(self, inst, running):
        for pkg, kern_pkg, headers_pkg, _ in KERNELS:
            btn_inst, btn_rem = self.kernel_rows[pkg]
            is_installed = kern_pkg in inst
            is_running   = kern_pkg.replace("linux-", "").replace("linux","") in running or kern_pkg in running
            btn_inst.set_sensitive(not is_installed)
            btn_rem.set_sensitive(is_installed and not is_running)
            btn_inst.set_label("✓ Installed" if is_installed else "⬇ Install")

    # ── packages tab helpers ──────────────────────────────────────────────────

    def _stat_widget(self, parent, num, lbl):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_hexpand(True); box.add_css_class("stat-box")
        n = Gtk.Label(label=num); n.add_css_class("stat-num"); n.set_halign(Gtk.Align.START)
        l = Gtk.Label(label=lbl); l.add_css_class("stat-lbl"); l.set_halign(Gtk.Align.START)
        box.append(n); box.append(l); parent.append(box)
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
        self.installed    = inst
        self.updates      = upds
        self.spinner.stop()
        self.status_row.set_visible(False)
        self._update_stats()
        self._filter()
        self._apply_kernel_button_states(inst, "")

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
                 and (self.filter_mode == "all" or self._pkg_status(p) == self.filter_mode)]
        for name in shown:
            self.list_box.append(self._make_row(name))

    def _make_row(self, name):
        st  = self._pkg_status(name)
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(10); box.set_margin_end(10); box.set_margin_top(8); box.set_margin_bottom(8)

        chk = Gtk.CheckButton(); chk.set_active(name in self.selected); chk.connect("toggled", self._on_check, name)
        box.append(chk)

        nm = Gtk.Label(label=name); nm.set_halign(Gtk.Align.START); nm.set_hexpand(True); nm.set_ellipsize(Pango.EllipsizeMode.END)
        attr = Pango.AttrList(); attr.insert(Pango.attr_family_new("monospace")); nm.set_attributes(attr)
        box.append(nm)

        badge = Gtk.Label()
        if st == "installed":
            badge.set_label("installed");        badge.add_css_class("badge-ins")
        elif st == "updates":
            badge.set_label("update available"); badge.add_css_class("badge-upd")
        else:
            badge.set_label("available");        badge.add_css_class("badge-avl")
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

    def _on_install(self, _):
        pkgs = list(self.selected); self.btn_install.set_sensitive(False)
        def done(rc):
            if rc == 0:
                self._term_print("✓ Installation complete.")
                self.selected.clear(); self._load_packages()
            else:
                self._term_print("✗ Installation failed.")
        self._run_pkexec(["pacman", "-S", "--needed", "--noconfirm"] + pkgs, done)

    def _on_update(self, _):
        def done(rc):
            if rc == 0:
                self._term_print("✓ System updated successfully."); self._load_packages()
            else:
                self._term_print("✗ Update failed.")
        self._run_pkexec(["pacman", "-Syu", "--noconfirm"], done)

    def _on_sync(self, _):
        def done(rc):
            if rc == 0:
                self._term_print("✓ Database synchronized."); self._load_packages()
            else:
                self._term_print("✗ Sync failed.")
        self._run_pkexec(["pacman", "-Sy"], done)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    app = PkgManagerApp()
    sys.exit(app.run(sys.argv))
