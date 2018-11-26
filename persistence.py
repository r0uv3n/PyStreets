import array
import os
import pickle
import zlib

from settings import settings


def persist_serialize(data, compress=True):
    """This function serializes and compresses an object"""
    if compress:
        return zlib.compress(pickle.dumps(data))
    else:
        return pickle.dumps(data)


def persist_deserialize(data, compressed=True):
    """This function deserializes and decompresses an object"""
    if compressed:
        return pickle.loads(zlib.decompress(data))
    else:
        return pickle.loads(data)


def persist_write(filename, data, compress=True, is_array=False, sub_dir=""):
    """This function saves a data structure to a file"""
    filename = settings['persistent_files_dir'] + sub_dir + filename
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "wb") as f:
        if is_array:
            data.tofile(f)
        else:
            f.write(persist_serialize(data, compress))


def persist_read(filename, compressed=True, is_array=False, sub_dir=""):
    """This function reads a data structure from a file"""
    filename = settings['persistent_files_dir'] + sub_dir + filename
    with open(filename, "rb") as f:
        data = f.read()
    if is_array:
        result = array.array("I")
        result.frombytes(data)
    else:
        result = persist_deserialize(data, compressed)
    return result
