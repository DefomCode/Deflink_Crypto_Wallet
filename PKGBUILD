pkgname=dcw
pkgver=0.1.0
pkgrel=2
pkgdesc="Автономный CLI-менеджер холодных крипто-кошельков (ETH + TRX)"
arch=('any')
url="https://github.com/DefomCode/Deflink_Crypto_Wallet"
license=('custom:non-commercial')
depends=('python-pipx' 'git')
install='dcw.install'
source=("git+${url}.git#tag=v${pkgver}")
sha256sums=('SKIP')

package() {
    cd "$srcdir/Deflink_Crypto_Wallet"

    # Создаём прокси-скрипт на случай если pipx ещё не установился
    mkdir -p "$pkgdir/usr/bin"
    cat > "$pkgdir/usr/bin/dcw" << 'PROXYEOF'
#!/bin/bash
VENV_BIN="$HOME/.local/share/pipx/venvs/dcw/bin/dcw"
if [ -f "$VENV_BIN" ]; then
    exec "$VENV_BIN" "$@"
else
    echo "⚠️  DCW ещё не установлен через pipx."
    echo "   Подождите завершения post-install хука или выполните:"
    echo "   pipx install git+https://github.com/DefomCode/Deflink_Crypto_Wallet.git"
    exit 1
fi
PROXYEOF
    chmod 755 "$pkgdir/usr/bin/dcw"

    # Документация и лицензия
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
    install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
    install -Dm644 SECURITY.md "$pkgdir/usr/share/doc/$pkgname/SECURITY.md"
}
