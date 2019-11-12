# framework-esp8266-rtos-sdk-idf-platformio
There are several ways to compile a project if windows
VSCODE 

# 1 compile with idf.py

1.1 Add Environment variable IDF_PATH={path to FRAMEWORK_DIR}. add {path to FRAMEWORK_DIR} to PATH

1.2 install [CMAKE for Windows](https://cmake.org/download/), [NINJA](https://github.com/ninja-build/ninja/releases), [MCONF](https://github.com/espressif/kconfig-frontends/releases/)

1.3 add path to cmake/bin, mconf, ninja to PATH

1.4 install python requirements from requirements.txt

1.5 Rename SRC Dir to MAIN Dir

1.6 Add to project root file CMakeLists.txt
```
cmake_minimum_required(VERSION 3.5)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project({project-name})
```

1.7 add to MAIN dir file CMakeLists.txt
```
file(GLOB SOURCES "*.c")
set(COMPONENT_SRCS "${SOURCES}")
register_component()
```

1.8 from vscode terminal run %IDF_PATH%/tools/idf.py build (or flash)

to get more documentation on idf.py run idf.py without parameters

to configure project use create file sdkconfig.defaults in project root



# 2 compile with cmake

https://docs.espressif.com/projects/esp-idf/en/latest/api-guides/build-system.html#using-cmake-directly

# 3 compile with make