# framework-esp8266-rtos-sdk-idf-platformio
This is PLATFORM package for platformio.

```ini
[env:stable]
platform = custom8266
framework = esp8266-rtos-sdk
board = ...
...
```

Package include
- builder scrypt for framework https://github.com/espressif/ESP8266_RTOS_SDK.git master
- toolchain [Windows](https://dl.espressif.com/dl/xtensa-lx106-elf-win32-1.22.0-92-g8facf4c-5.2.0.tar.gz)

builder scrypt test only
- board 4M
- CONFIG_PARTITION_TABLE_SINGLE_APP
- flash over USB CP2102 (and similar)

features such as secureboot, OTA, flash less than 4M - NOT TESTED!!
