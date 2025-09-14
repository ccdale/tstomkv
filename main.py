import tstomkv
from tstomkv.files import remoteFileList


def main():
    print(f"{tstomkv.__appname__} version: {tstomkv.getVersion()}")
    files = remoteFileList()
    print(f"{len(files)} Remote files")
    for f in files:
        print(f" - {f}")


if __name__ == "__main__":
    main()
