# Copyright 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Espressif IDF

Espressif IoT Development Framework for ESP32 MCU

https://github.com/espressif/esp-idf
"""

from glob import glob
from os import listdir, walk
from os.path import abspath, basename, isdir, isfile, join

from shutil import copy
import sys
from SCons.Script import DefaultEnvironment
import shlex
import click
print(click.style("To compile project see README.md", fg="red"))
exit(1)

env = DefaultEnvironment()
platform = env.PioPlatform()
FRAMEWORK_NAME = "framework-"+env.subst('$PIOFRAMEWORK')
FRAMEWORK_DIR = platform.get_package_dir(FRAMEWORK_NAME)
env.Replace(FRAMEWORK_DIR=FRAMEWORK_DIR)

env.SConscript("_bare.py", exports="env")
env.SConscript("_embedtxt_files.py", exports="env")

def noop(**kwargs):
    return True

def check_ifdef(**kwargs):
    token=kwargs['token']
    ret=False
    if(len(token)<2):
        raise ValueError("ifdef few parameters", token)
    if(token[1] in env['SDKCONFIG']):
        ret=True
    elif(token[1] in kwargs['result']):
        ret=True
    return ret

def check_ifndef(**kwargs):
    return(not check_ifdef(**kwargs))

def parse_var(ln, **kwargs):
    nodes = {
        '$':[{'node_cur':0, 'node_next':1}, {'node_cur':5, 'node_next':1}],
        '(':[{'node_cur':1, 'node_next':2, 'var':1}],
        ')':[{'node_cur':2, 'node_next':0, 'end':1}],
    }
    node=0
    end=0
    var=None
    ln_new=''
    for c in ln:
        p=nodes.get(c,None)
        if(p is not None):
            state=None
            for k in p:
                if(node==k['node_cur']):
                    state=k
                    break
            if(state is None):
                print(click.style("Error parse var", fg="red"))
                print(ln, c, p, node)
                return ln
#                raise ValueError("parse_var err", ln, c, p, node)
            end=state.get('end',0)
            node=state['node_next']
            if(end):
                if(var in kwargs['result']):
                    x=kwargs['result'][var]
                    if(type(x) == list): ln_new = ln_new+" ".join(x)
                    else: ln_new = ln_new+x
                else:
                    ln_new = ln_new+'$('+var+')'
                var = None
                continue
            if('var' in state): var=''
            else: var=None
            if('add' in state): ln_new=ln_new+c
            continue
        if(var is not None):
            var=var+c
            continue
        node=0
        ln_new=ln_new+c
    return ln_new

def parse_args(ln):
    nodes = {
        '(':[{'node_cur':0, 'node_next':1},{'node_cur':2, 'node_next':3, 'arg':'arg1'}],
        '$':[{'node_cur':1, 'node_next':2}],
        ')':[{'node_cur':3, 'node_next':4},{'node_cur':5, 'node_next':6, 'end':1}],
        ',':[{'node_cur':4, 'node_next':5, 'arg':'arg2'}],
    }
    node=0
    end=0
    arg=None
    args={}
    for c in ln:
        p=nodes.get(c,None)
        if(p is not None):
            state=None
            for k in p:
                if(node==k['node_cur']):
                    state=k
                    break
            if(state is None):
                print(click.style("Error parse var", fg="red"))
                print(ln, c, p, node)
                return ln
#                raise ValueError("ifeq err", ln, c, p)
            end=state.get('end',0)
            if(end): break
            node=state['node_next']
            if('arg' in state):
                arg=state['arg']
                args[arg]=''
            else: arg=None
            continue
        if(arg is not None):
            args[arg]=(args[arg]+c).strip()
    return args

def check_ifeq(**kwargs):
    ret = False
    token = kwargs['token']
    ln = " ".join(x for x in token[1:])
    args = parse_args(ln)
    if('arg1' in args):
        arg_sdkconfig=env['SDKCONFIG'].get(args['arg1'], None)
        arg_result=kwargs['result'].get(args['arg1'], [])
        if(args['arg2']==arg_sdkconfig or args['arg2'] in arg_result):
            ret=True
    return ret

def check_ifneq(**kwargs):
    return not check_ifeq(**kwargs)

def parse_mk(path, **kwargs):
    result = {}
    variable = None
    multi = False
    conditionkey={
        'ifeq': {'oper':'+', 'func':check_ifeq},
        'ifneq': {'oper':'+', 'func':check_ifneq},
        'ifdef': {'oper':'+', 'func':check_ifdef},
        'ifndef': {'oper':'+', 'func':check_ifndef},
        'else':{'oper':'=', 'func':noop},
        'endif':{'oper':'-', 'func':noop},
    }
    stack=[]
    condition=True
    if('SET' in kwargs):
        result.update(kwargs['SET'])
#    print("start", condition, path)
    with open(path) as fp:
        for line in fp.readlines():
            line = line.strip()
            if not line or line.startswith("#"):
                multi = False
                continue
            # remove inline comments
            if " #" in line:
                line = line[:line.index(" #")]
            token = line.split()
            if(token[0] in conditionkey):
                oper=conditionkey[token[0]]['oper']
#                print(token, oper)
                if(oper=='+'):
                    kwargs={'token':token, 'result':result}
                    condition=conditionkey[token[0]]['func'](**kwargs)
                    stack.append({'condition':condition})
#                    print(token, oper, condition)
                elif(oper=='-'):
                    if(len(stack)==0):
                        raise ValueError("endif before if!!")
                    stack.pop()
                    if(len(stack)>0): condition=stack[-1]['condition']
                    else: condition=True
                elif(oper=='='):
                    stack[-1]['condition']=not condition
                    condition=True
                    for p in stack:
                        condition = condition and p['condition']
#                print(condition, stack)
                continue
            if(not condition):
                variable = None
                continue
            if not multi and "=" in line:
                add=False
                variable, line = line.split("=", 1)
                if variable.endswith((":", "+")):
                    if variable.endswith("+"):
                        add = True
                    variable = variable[:-1]
                variable = variable.strip()
                line = line.strip()
                if variable not in result or not add:
                    result[variable] = []
            if not variable or not line:
                continue
            multi = line.endswith('\\')
            if multi:
                line = line[:-1].strip()
            kwargs={'token':token, 'result':result}
            line = parse_var(line, **kwargs)
            line = line.replace("-L ", "-L")
            line = line.replace("'\"", "\\\"")
            line = line.replace("\"'", "\\\"")
            result[variable].extend([l.strip() for l in line.split()])
            if not multi:
                variable = None
#    print("result", result)
    return result

def parse_define(path):
    result = {}
    variable = None
    with open(path) as fp:
        for line in fp.readlines():
            line = line.strip()
            if line.startswith("#define"):
		line = line.replace('"','')
                _, variable, line = line.split(" ", 2)
                variable = variable.strip()
                try:
                      line=int(line)
                except:
                      pass
            if not variable:
                continue
            result[variable] = line
            variable = None
    return result

def build_comp(envs, path, **kwargs):
    src_filter = "+<*.[sSc]*> -<test*>"
    incl=join(path, "include")
    if(isdir(incl)):
        envs.AppendUnique(CPPPATH=[incl])
    files=["component.mk", "Makefile.projbuild"]
    exclude=[("esp8266", "Makefile.projbuild"),]
    for f in files:
        comp = path[path.rfind('\\')+1:]
        if((comp,f) in exclude): continue
        if(isfile(join(path, f))):
            params = parse_mk(join(path, f), **kwargs)
            inc_dirs = params.get("COMPONENT_PRIV_INCLUDEDIRS")
            if inc_dirs:
                envs.PrependUnique(CPPPATH=[join(path, d.replace('/','\\')) for d in inc_dirs])
            inc_dirs = params.get("COMPONENT_ADD_INCLUDEDIRS")
            if inc_dirs:
                envs.AppendUnique(CPPPATH=[join(path, d.replace('/','\\')) for d in inc_dirs])
            inc_dirs = params.get("CFLAGS")
            if inc_dirs:
                envs.AppendUnique(CCFLAGS=inc_dirs)
            inc_dirs = params.get("CPPFLAGS")
            if inc_dirs:
                envs.AppendUnique(CCFLAGS=inc_dirs)
            inc_dirs = params.get("COMPONENT_ADD_LDFLAGS")
            if inc_dirs:
                envs.AppendUnique(COMPONENT_ADD_LDFLAGS=inc_dirs)
            if params.get("COMPONENT_OBJS"):
                src_filter = "-<*>"
                for f in params.get("COMPONENT_OBJS"):
                    src_filter += " +<%s>" % f.replace(".o", ".c")
            elif params.get("COMPONENT_SRCDIRS"):
                src_filter = "-<*>"
                src_dirs = params.get("COMPONENT_SRCDIRS")
                if "." in src_dirs:
                    src_dirs.remove(".")
                    src_filter += " +<*.[sSc]*>"
                for f in src_dirs:
                    src_filter += " +<%s/*.[sSc]*>" % f
            if params.get("COMPONENT_OBJEXCLUDE"):
                for f in params.get("COMPONENT_OBJEXCLUDE"):
                    src_filter += " -<%s>" % f.replace(".o", ".c")
    return src_filter

def find_valid_config_file():
    search_path = join(
        platform.get_dir(), "examples", "sdkconfig.h")
    files = glob(search_path)
    if not files:
        sys.stderr.write(
            "Error: Could not find default \"sdkconfig.h\" file\n")
        env.Exit(1)
    return files[0]

def libesp8266(envsaf, is_bootloader_build):
    envsaf.PrependUnique(
        CPPPATH=[
            join(FRAMEWORK_DIR, "components", "esp8266", "include"),
        ],
    )
#    envsaf.Replace(
#        LINKER_SCRIPTS=[
#            "-Tesp8266.rom.ld",
#            "-Tesp8266.peripherals.ld",
#        ],
#        COMPONENT_ADD_LDFLAGS=[
##        "-L$COMPONENT_PATH/lib",
##        "$(addprefix -l,$(LIBS))",
##        "-L$COMPONENT_PATH/ld",
#            "-Tesp8266_out.ld",
#            "-Tesp8266_common_out.ld",
#            "-Wl,--no-check-sections",
#            "-u", "call_user_start",
#            "$LINKER_SCRIPTS",
#        ],
#    )
    envsaf.AppendUnique(
        LIBS=[
            "gcc", "hal", "core", "net80211", "phy", "pp", "smartconfig", "ssc", "wpa", "espnow", "wps",
        ],
    )
    if(is_bootloader_build):
        filt="+<source/ets_printf.c>"
#        envsaf.Replace(
#            CPPPATH=[
#                join(FRAMEWORK_DIR, "components", "esp8266", "source", "ets_printf.c"),
#            ],
#        )
    else:
        filt="+<driver/*> +<source/*>"
        envsaf.AppendUnique(
            CPPPATH=[
                join(FRAMEWORK_DIR, "components", "esp8266", "include", "driver"),
#                join(FRAMEWORK_DIR, "components", "esp8266", "driver"),
#                join(FRAMEWORK_DIR, "components", "esp8266", "source"),
            ],
        )
    return filt

def build_espidf_bootloader():
    envsafe = env.Clone()
    envsafe.AppendUnique(
        CPPDEFINES=[("BOOTLOADER_BUILD",1)]
    )
    envsafe.AppendUnique(
        CPPFLAGS=["-DIS_BOOTLOADER_BUILD=1"]
    )
    envsafe.Replace(
        LIBPATH=[
            join(FRAMEWORK_DIR, "components", "esp8266", "ld"),
            join(FRAMEWORK_DIR, "components", "esp8266", "lib"),
            join("$BUILD_DIR", "bootloader")
        ],
    )
    envsafe.AppendUnique(
        CPPPATH=[
#            join(FRAMEWORK_DIR, "components", "esp8266"),
            join(FRAMEWORK_DIR, "components", "bootloader_support", "include"),
            join(FRAMEWORK_DIR, "components", "bootloader_support", "include_priv"),
        ]
    )

#    kwargs={'SET':{"IS_BOOTLOADER_BUILD":1, 'COMPONENT_PATH':join(FRAMEWORK_DIR, "components", "newlib")}}
#    ee = parse_mk(join(FRAMEWORK_DIR, "components", "newlib", "component.mk"), **kwargs)
#    print("test", ee)

    libs=[]
    lib_build=[]

    components = ("esp8266", "log", "util", "spi_flash", "bootloader_support")
#    libs=["core", "c", "gcc", "stdc++", "hal"]
    for d in components:
        build_dir = join("$BUILD_DIR", "bootloader", d)
        component_dir = join(FRAMEWORK_DIR, "components", d)
        if(d=="esp8266"):
            filt = libesp8266(envsafe, 1)
            lib_build.append((d, filt+" -<test*>"))
#        elif(d=="spi_flash"):
#            filt = libspi_flash(envsafe, 1)
#            lib_build.append((d, filt+" -<test*>"))
        elif(isdir(component_dir)):
            kwargs={'SET':{"IS_BOOTLOADER_BUILD":1, 'COMPONENT_PATH':component_dir}}
            lib_build.append((d, build_comp(envsafe, component_dir, **kwargs)))

    for d, filt in lib_build:
        build_dir = join("$BUILD_DIR", "bootloader", d)
        component_dir = join(FRAMEWORK_DIR, "components", d)
        libs.append(
            envsafe.BuildLibrary(build_dir,component_dir,src_filter=filt,)
        )
    envsafe.Replace(
        LIBS=libs,
        MAP=[
            "-Wl,-Map=\"$BUILD_DIR/bootloader.map\"",
        ],
        COMPONENT_PATH=[
            join(FRAMEWORK_DIR, "components", "bootloader", "subproject", "main"),
        ],
        LINKER_SCRIPTS=[
            "-Tesp8266.bootloader.ld",
            "-T$IDF_PATH/components/esp8266/ld/esp8266.rom.ld",
            "-Tesp8266.bootloader.rom.ld",

        ],
        COMPONENT_ADD_LDFLAGS="-L$IDF_PATH/components/esp8266/lib -lcore -L$COMPONENT_PATH $LINKER_SCRIPTS",
    )
    return envsafe.Program(
        join("$BUILD_DIR", "bootloader.elf"),
        envsafe.CollectBuildFiles(
            join("$BUILD_DIR", "bootloader"),
            join(FRAMEWORK_DIR, "components", "bootloader", "subproject", "main")
        )
    )

def search_file(filename, search_path):
    """ Given a search path, find file with requested name """
    for path in search_path:
        candidate = join(path, filename)
        if isfile(candidate): return abspath(candidate)
    return None

###################################################
#
# Handle missing sdkconfig.h
#

if not isfile(join(env.subst("$PROJECTSRC_DIR"), "sdkconfig.h")):
    print(click.style("Warning! Cannot find \"sdkconfig.h\" file. "
          "Default \"sdkconfig.h\" will be added to your project!", fg="red"))
    copy(find_valid_config_file(), join(env.subst("$PROJECTSRC_DIR"), "sdkconfig.h"))
else:
    is_new = False
    with open(join(env.subst("$PROJECTSRC_DIR"), "sdkconfig.h")) as fp:
        for l in fp.readlines():
            if "CONFIG_PARTITION_TABLE_OFFSET" in l:
                is_new = True
                break

    if not is_new:
        print("Warning! Detected an outdated \"sdkconfig.h\" file. "
              "The old \"sdkconfig.h\" will be replaced by the new one.")

        new_config = find_valid_config_file()
        copy(
            join(env.subst("$PROJECTSRC_DIR"), "sdkconfig.h"),
            join(env.subst("$PROJECTSRC_DIR"), "sdkconfig.h.bak")
        )
        copy(new_config, join(env.subst("$PROJECTSRC_DIR"), "sdkconfig.h"))
sdkconfig=parse_define(join(env.subst("$PROJECTSRC_DIR"), "sdkconfig.h"))
env.Replace(
     SDKCONFIG=sdkconfig,
)

#
# Generate linker script
#

env.Replace(
    OUTLD_CFLAGS=[
        "-DAPP_OFFSET=CONFIG_APP1_OFFSET",
        "-DAPP_SIZE=CONFIG_APP1_SIZE",
    ]
)
linker_script = env.Command(
    join("$BUILD_DIR", "esp8266_out.ld"),
    join(FRAMEWORK_DIR, "components", "esp8266", "ld", "esp8266.ld"),
    env.VerboseAction(
#	$(CC) $(OUTLD_CFLAGS) -I ../include -C -P -x c -E $< -o $@ #origin
        '$CC $OUTLD_CFLAGS -I"$PROJECTSRC_DIR" -P -x c -E $SOURCE -o $TARGET',
        "Generating LD script $TARGET")
)
env.Depends("$BUILD_DIR/$PROGNAME$PROGSUFFIX", linker_script)

linker_script = env.Command(
    join("$BUILD_DIR", "esp8266_common_out.ld"),
    join(FRAMEWORK_DIR, "components", "esp8266", "ld", "esp8266.common.ld"),
    env.VerboseAction(
#	$(CC) -I ../include -C -P -x c -E $< -o $@ #origin
        '$CC -I"$PROJECTSRC_DIR" -P -x c -E $SOURCE -o $TARGET',
        "Generating LD script $TARGET")
)
env.Depends("$BUILD_DIR/$PROGNAME$PROGSUFFIX", linker_script)

env.PrependUnique(
    CPPPATH=[
        join("$PROJECTSRC_DIR"),
        join(FRAMEWORK_DIR, "components"),
    ],

    LIBPATH=[
        join(FRAMEWORK_DIR, "components", "esp8266"),
        join(FRAMEWORK_DIR, "components", "esp8266", "ld"),
        join(FRAMEWORK_DIR, "components", "esp8266", "lib"),
        "$BUILD_DIR"
    ],

    LIBS=[
        "hal", "core", "net80211", "espnow", "wps", "pp", "phy", "wpa",
    ],
    IDF_PATH=join(FRAMEWORK_DIR),
)

env.Prepend(
    CFLAGS=[
#        "-Wno-old-style-declaration"
        "-Wno-unknown-pragmas", #libsodium
    ],
    CPPFLAGS=[
        "-MMD",
        "-MP",
    ],
    CPPDEFINES=[
#        ("__ESP_FILE__", "\\\"null\\\""),
        ("__ESP_FILE__", "__FILE__"),
        "WITH_POSIX",
        "ESP_PLATFORM",
        ("IDF_VER", '\\"%s\\"' %
         platform.get_package_version(FRAMEWORK_NAME)),
    ],

    CCFLAGS=[
#        "-Werror=all",
#        "-Wno-error=deprecated-declarations",
#        "-Wextra",
#        "-Wno-unused-parameter",
#        "-Wno-sign-compare",
#        "-Wno-error=unused-function"
    ],
)

env.Append(
    LINKFLAGS_PRE=[
            "-nostdlib",
            "-u", "call_user_start_cpu0",
            "-Wl,--gc-sections",
            "-Wl,-static",
            "-Wl,--start-group",
#            "-T", "esp8266_out.ld",
#            "-T", "esp8266_common_out.ld",
#            "-Wl,--no-check-sections",
#            "-u", "call_user_start",
#            "-T", "esp8266.rom.ld",
#            "-T", "esp8266.peripherals.ld",
    ],
    LINKFLAGS_POST=[
        "-lgcc", "-lstdc++", "-lgcov",
        "-Wl,--end-group",
	    "-Wl,-EL",
    ],
    MAP=[
        "-Wl,-Map=\"$BUILD_DIR/${PROGNAME}.map\"",
    ],

    FLASH_EXTRA_IMAGES=[
##        ("0x1000", join("$BUILD_DIR", "bootloader.bin")),
        ("0x0000", join("\"$BUILD_DIR\"", "bootloader.bin")),
        ("0x8000", join("\"$BUILD_DIR\"", "partitions.bin"))
    ]
)
env['__LIBFLAGS']='${_stripixes(LIBLINKPREFIX, LIBS, LIBLINKSUFFIX, LIBPREFIXES, LIBSUFFIXES, __env__)}' 
env['LINKCOM'] = '$LINK $LINKFLAGS_PRE $_LIBDIRFLAGS $__LIBFLAGS $COMPONENT_ADD_LDFLAGS $__RPATH $SOURCES $LINKFLAGS_POST -o $TARGET $MAP'
#env['LINKCOM'] = '$LINK $LINKFLAGS_PRE $_LIBDIRFLAGS $__LIBFLAGS $COMPONENT_ADD_LDFLAGS $LINKFLAGS_POST -o $TARGET $MAP'


env.Replace(
    LINKER_SCRIPTS=[
        "-Tesp8266.rom.ld",
        "-Tesp8266.peripherals.ld",
    ],
    COMPONENT_ADD_LDFLAGS=[
#        "-L$COMPONENT_PATH/lib",
#        "$(addprefix -l,$(LIBS))",
#        "-L$COMPONENT_PATH/ld",
        "-Tesp8266_out.ld",
        "-Tesp8266_common_out.ld",
        "-Wl,--no-check-sections",
        "-u", "call_user_start",
        "$LINKER_SCRIPTS",
    ],
)

if "PIO_FRAMEWORK_ESP_IDF_ENABLE_EXCEPTIONS" in env.Flatten(
        env.get("CPPDEFINES", [])):

    # remove unnecessary flag defined in main.py that disables exceptions
    try:
        index = env['CXXFLAGS'].index("-fno-exceptions")
        if index > 0:
            env['CXXFLAGS'].remove("-fno-exceptions")
    except IndexError:
        pass

    env.Append(
        CPPDEFINES=[
            ("CONFIG_CXX_EXCEPTIONS", 1),
            ("CONFIG_CXX_EXCEPTIONS_EMG_POOL_SIZE", 0)
        ],

        CXXFLAGS=["-fexceptions"]
    )

else:
    env.Append(LINKFLAGS=["-u", "__cxx_fatal_exception"])


#
# ESP-IDF doesn't need assembler-with-cpp option
#

env.Replace(ASFLAGS=[])

#
# Generate partition table
#

search_path = [
                join(FRAMEWORK_DIR, "components", "partition_table"),
                join(env.subst("$PROJECTSRC_DIR")),
              ]
if('CONFIG_PARTITION_TABLE_CUSTOM_FILENAME' in env['SDKCONFIG']):
    partitions_csv = env['SDKCONFIG']['CONFIG_PARTITION_TABLE_CUSTOM_FILENAME']
else:
    partitions_csv = env['SDKCONFIG']['CONFIG_PARTITION_TABLE_FILENAME']
partitions_csv = env.BoardConfig().get("build.partitions", partitions_csv)
full_partitions_csv=search_file(partitions_csv, search_path)
env.Replace(
    PARTITIONS_TABLE_CSV=full_partitions_csv if full_partitions_csv and isfile(full_partitions_csv) else abspath(partitions_csv))

partition_table = env.Command(
    join("$BUILD_DIR", "partitions.bin"),
    "$PARTITIONS_TABLE_CSV",
    env.VerboseAction('"$PYTHONEXE" "%s" -q $SOURCE $TARGET' % join(
        FRAMEWORK_DIR, "components", "partition_table", "gen_esp32part.py"),
        "Generating partitions $TARGET"))
env.Depends("$BUILD_DIR/$PROGNAME$PROGSUFFIX", partition_table)

#
# Compile bootloader
#

env.Depends("$BUILD_DIR/$PROGNAME$PROGSUFFIX", env.ElfToBin(
    join("$BUILD_DIR", "bootloader"), build_espidf_bootloader()))

#
# Target: Build Core Library
#

libs = []
lib_build=[]

build_dirs = [
    "esp8266", "util", "nvs_flash", "newlib", "openssl", "bootloader_support", "log",
    "esp-tls", "lwip", "tcpip_adapter", "spi_flash", "heap", "freertos",
    "app_update", "json", "wpa_supplicant", 
    "coap", "esp_http_client", "esp_http_server", "tcp_transport", "http_parser", 
    "jsmn", "protobuf-c", "pthread", "smartconfig_ack", "spiffs", "vfs", "mdns", 
    "libsodium", "mqtt",
    "aws_iot",  
    "esp_https_ota", "protocomm", "wifi_provisioning",
    "esp_ringbuf", "console", "spi_ram", "mbedtls", "esp_common", 
]
#"esp_https_server", 
build_excl = [
    "bootloader", "esptool_py", "partition_table",
]
lib_ignore=env.GetProjectOption("lib_ignore", [])

if isdir("c:\\users\\test"):
	k = build_dirs+build_excl
	new_lib=[]
	for p in listdir(join(FRAMEWORK_DIR, "components")):
	    if(isdir(join(FRAMEWORK_DIR, "components", p))):
        	if(p not in k):
                    if p not in lib_ignore: new_lib.append(p)
        	else: k.remove(p)
	if(new_lib or k):
	    print("%s %s\n%s %s" %(
		click.style("New lib: ", fg="red", bold=True),
		", ".join(new_lib),
		click.style("Lib not found: ", fg="red", bold=True),
		", ".join(k),
                )
	    )
	    env.Exit(1)

for d in build_dirs:
    if d in lib_ignore: continue
    build_dir = join("$BUILD_DIR", d)
    component_dir = join(FRAMEWORK_DIR, "components", d)
    if(d=="esp8266"):
        filt = libesp8266(env, 0)
        lib_build.append((d,filt+" -<test*>"))
    elif(isdir(component_dir)):
        kwargs={'SET':{'COMPONENT_PATH':component_dir}}
        lib_build.append((d, build_comp(env, component_dir, **kwargs)))

for d,filt in lib_build:
    build_dir = join("$BUILD_DIR", d)
    component_dir = join(FRAMEWORK_DIR, "components", d)
    envsafe = env.Clone()
    if(d=="ssl"):
        envsafe.Append(
           CFLAGS=[
             "-Wno-maybe-uninitialized", 
           ],
        )
    libs.append(
        envsafe.BuildLibrary(build_dir, component_dir, src_filter=filt),
    )
    
env.Append(LIBS=libs)
#print(env.Dump())