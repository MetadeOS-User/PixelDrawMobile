[app]

# ---- Identificação -------------------------------------------------------
title = PixelDraw
package.name = pixeldraw
package.domain = org.pixeldraw
version = 1.0.0

# ---- Código-fonte --------------------------------------------------------
source.dir = .
source.include_exts = py,png
source.exclude_dirs = .git,.github,.buildozer,bin,__pycache__,tests

# ---- Dependências --------------------------------------------------------
# O PNG é gerado com zlib/struct (biblioteca padrão), então não precisa de Pillow.
requirements = python3,kivy==2.3.0,pyjnius,android

# ---- Aparência -----------------------------------------------------------
icon.filename = %(source.dir)s/icon.png
orientation = portrait
fullscreen = 0

# ---- Android -------------------------------------------------------------
# Só Android 9 ou inferior precisa dessa permissão. No 10+ o app salva pelo
# MediaStore (aparece na Galeria, em Imagens/PixelDraw) sem pedir nada.
android.permissions = (name=android.permission.WRITE_EXTERNAL_STORAGE;maxSdkVersion=28)

# Versão mínima: API 21 = Android 5.0. Isso inclui o Android 5.1.1 (API 22).
# 21 também é o menor valor que o python-for-android aceita (não dá para baixar).
# Não aumente minapi/ndk_api se precisar continuar rodando no 5.1.1.
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.ndk = 25b

# 32 bits (armeabi-v7a) + 64 bits (arm64-v8a) no MESMO apk.
# O Android escolhe sozinho a versão certa para cada aparelho.
android.archs = arm64-v8a, armeabi-v7a

android.accept_sdk_license = True
android.allow_backup = True

# Versão do python-for-android fixada (combina com NDK 25b e Kivy 2.3.0)
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
