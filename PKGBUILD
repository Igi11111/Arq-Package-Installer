# Maintainer: Igi <igi@arqos>
pkgname=arq-pkg-manager
pkgver=1.0.0
pkgrel=3
pkgdesc="Graphical package manager for ArqOS — arq-repo repository (GTK4/Python)"
arch=('any')
url="https://github.com/Igi11111/ArqOS"
license=('GPL3')
depends=('python' 'python-gobject' 'gtk4' 'polkit')
optdepends=('xdg-desktop-portal-kde: dark theme integration on KDE Plasma'
            'pacman-contrib: full update detection support')
source=("arq-pkg-manager.py"
        "arq-pkg-manager.desktop"
        "arq-pkg-manager.png"       # taskbar / menu icon  (matches APP_ID)
        "arq-pkg-manager-logo.png") # in-app header icon   (can be different)
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
    install -Dm755 "$srcdir/arq-pkg-manager.py" \
        "$pkgdir/usr/bin/arq-pkg-manager"

    install -Dm644 "$srcdir/arq-pkg-manager.desktop" \
        "$pkgdir/usr/share/applications/arq-pkg-manager.desktop"

    # Taskbar / menu icon — name must match APP_ID in the script
    for size in 16 22 24 32 48 64 128 256; do
        install -Dm644 "$srcdir/arq-pkg-manager.png" \
            "$pkgdir/usr/share/icons/hicolor/${size}x${size}/apps/arq-pkg-manager.png"
    done

    # In-app header logo — separate file, can be any artwork
    for size in 32 48 64 128 256; do
        install -Dm644 "$srcdir/arq-pkg-manager-logo.png" \
            "$pkgdir/usr/share/icons/hicolor/${size}x${size}/apps/arq-pkg-manager-logo.png"
    done
}
