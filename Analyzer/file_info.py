"""Metadata lookup for files in an EXT4 image."""

from ext4 import Ext4Image


class FileInfo:
    """Retrieve inode and extent metadata through an existing ``Ext4Image``."""

    def __init__(self, fs: Ext4Image):
        self.fs = fs

    def get_info(self, path: str):
        inode_number = self.fs.path_to_inode(path)

        if inode_number is None:
            raise FileNotFoundError(path)

        raw_inode = self.fs.read_inode(inode_number)
        inode = self.fs.parse_inode(raw_inode)
        extents = self.fs.extents.get_extents(raw_inode)
        mode = inode["mode"]

        return {
            "path": path,
            "inode": inode_number,
            "type": self._file_type(mode),
            "size": inode["size"],
            "blocks": inode["blocks"],
            "links": inode["links"],
            "uid": inode["uid"],
            "gid": inode["gid"],
            "mode": mode,
            "permissions": self._permissions(mode),
            "flags": inode["flags"],
            "extent_count": len(extents),
            "extent_blocks": sum(extent["length"] for extent in extents),
            "atime": inode["atime"],
            "mtime": inode["mtime"],
            "ctime": inode["ctime"],
        }

    @staticmethod
    def _file_type(mode: int) -> str:
        return "directory" if mode & 0o170000 == 0o040000 else "file"

    @classmethod
    def _permissions(cls, mode: int) -> str:
        permissions = [
            "d" if cls._file_type(mode) == "directory" else "-",
        ]

        for read, write, execute in (
            (0o400, 0o200, 0o100),
            (0o040, 0o020, 0o010),
            (0o004, 0o002, 0o001),
        ):
            permissions.extend((
                "r" if mode & read else "-",
                "w" if mode & write else "-",
                "x" if mode & execute else "-",
            ))

        return "".join(permissions)
