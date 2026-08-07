from ctypes import *
from ctypes.wintypes import *

BROTLI_MAGIC = b'\x1e\x9b'
GZIP_MAGIC = b'\x1f\x8b'
JPEG_MAGIC = b'\xff\xd8'
LOTTIE_MAGIC = b'LOTTIE'
PNG_MAGIC = b'\x89\x50\x4E\x47'
WOFF_MAGIC = b'wOF2'
ZIP_MAGIC = b'PK\x03\x04'

AVIF_MAGIC = b'ftypavif'
AVIF_OFFSET = 4

MP4_MAGIC = b'ftypmp4'
MP4_OFFSET = 4

WEBP_MAGIC = b'WEBP'
WEBP_OFFSET = 8

# // v4 header: uint32(version), uint32(resource_count), uint8(encoding)
#class HEADER_V4(Structure):
#    _pack_ = 1
#    _fields_ = [
#        ("version",         UINT),
#        ("resource_count",  UINT),
#        ("encoding",        BYTE),
#    ]

# 12 bytes
class HEADER_V5_16(Structure):
    _fields_ = [
        ("version",         UINT),
        ("encoding",        UINT),
        ("resource_count",  USHORT),
        ("alias_count",     USHORT),
    ]

# 16 bytes
class HEADER_V5_32(Structure):
    _fields_ = [
        ("version",         UINT),
        ("encoding",        UINT),
        ("resource_count",  UINT),
        ("alias_count",     UINT),
    ]

# 6 bytes
class RESOURCE_ENTRY_16(Structure):
    _pack_ = 2
    _fields_ = [
        ("resource_id",     USHORT),
        ("offset",          UINT),
    ]

# 8 bytes
class RESOURCE_ENTRY_32(Structure):
    _fields_ = [
        ("resource_id",     UINT),
        ("offset",          UINT),
    ]

# 4 bytes
class ALIAS_ENTRY_16(Structure):
    _fields_ = [
        ("resource_id",     USHORT),
        ("index",           USHORT),
    ]

# 8 bytes
class ALIAS_ENTRY_32(Structure):
    _fields_ = [
        ("resource_id",     UINT),
        ("index",           UINT),
    ]

class PakInfos:
    def __init__(self, header: object):  #id_size
        self.header = header
        self.is_32bit = type(header) == HEADER_V5_32
        self.resource_table = {}
        self.alias_table = {}
