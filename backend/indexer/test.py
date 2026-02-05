import indexer


def main():
    encoded_bytes = indexer.encode_vbytes(8675309)
    decoded_int, bytes_read = indexer.decode_vbytes(encoded_bytes)
    print(decoded_int)


if __name__ == "__main__":
    main()
