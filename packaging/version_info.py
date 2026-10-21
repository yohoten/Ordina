# Ordina — Windows 可执行文件版本资源（PyInstaller --version-file 用）
#
# 注意：PyInstaller 6.x 用 eval() 解析本文件，只接受「单个表达式」，
#       因此不能有模块 docstring，说明只能写成 # 注释。
#
# 语言标识 2052 = 简体中文，1200 = UTF-16 代码页。
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(3, 0, 0, 0),
        prodvers=(3, 0, 0, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,        # VOS_NT_WINDOWS32
        fileType=0x1,      # VFT_APP
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "080404B0",
                    [
                        StringStruct("CompanyName", "yohoten"),
                        StringStruct("FileDescription", "Ordina / 归序 - 下载文件夹整理工具"),
                        StringStruct("FileVersion", "3.0.0"),
                        StringStruct("InternalName", "Ordina"),
                        StringStruct("LegalCopyright", "Copyright (c) 2026 yohoten"),
                        StringStruct("OriginalFilename", "Ordina.exe"),
                        StringStruct("ProductName", "Ordina / 归序"),
                        StringStruct("ProductVersion", "3.0.0"),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [2052, 1200])]),
    ],
)
