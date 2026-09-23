FLAG = 0x7E


def bytes_to_lsb_bits(data):
    bits = []
    for value in data:
        for bit_index in range(8):
            bits.append((value >> bit_index) & 1)
    return bits


def lsb_bits_to_bytes(bits):
    if len(bits) % 8:
        raise ValueError("Bit count must be a multiple of eight")
    output = bytearray()
    for start in range(0, len(bits), 8):
        value = 0
        for bit_index, bit in enumerate(bits[start:start + 8]):
            value |= (bit & 1) << bit_index
        output.append(value)
    return bytes(output)


def bit_stuff(bits):
    output = []
    consecutive_ones = 0
    for bit in bits:
        output.append(bit)
        if bit:
            consecutive_ones += 1
            if consecutive_ones == 5:
                output.append(0)
                consecutive_ones = 0
        else:
            consecutive_ones = 0
    return output


def bit_unstuff(bits):
    output = []
    consecutive_ones = 0
    index = 0
    while index < len(bits):
        bit = bits[index]
        output.append(bit)
        index += 1
        if bit:
            consecutive_ones += 1
            if consecutive_ones == 5:
                if index >= len(bits) or bits[index] != 0:
                    raise ValueError("Invalid HDLC bit stuffing")
                index += 1
                consecutive_ones = 0
        else:
            consecutive_ones = 0
    return output


def nrzi_encode(bits, initial_level=1):
    level = initial_level
    output = []
    for bit in bits:
        if bit == 0:
            level ^= 1
        output.append(level)
    return output


def nrzi_decode(levels, initial_level=1):
    previous = initial_level
    bits = []
    for level in levels:
        bits.append(1 if level == previous else 0)
        previous = level
    return bits


def encode_hdlc_frame(ax25_frame, preamble_flags=32, trailer_flags=8):
    flag_bits = bytes_to_lsb_bits(bytes([FLAG]))
    frame_bits = bit_stuff(bytes_to_lsb_bits(ax25_frame))
    encoded = flag_bits * preamble_flags + frame_bits + flag_bits * trailer_flags
    return nrzi_encode(encoded)


def decode_hdlc_frames(nrzi_levels):
    bits = nrzi_decode(nrzi_levels)
    flag = bytes_to_lsb_bits(bytes([FLAG]))
    flag_positions = []
    for index in range(len(bits) - 7):
        if bits[index:index + 8] == flag:
            flag_positions.append(index)

    frames = []
    for first, second in zip(flag_positions, flag_positions[1:]):
        stuffed = bits[first + 8:second]
        if not stuffed:
            continue
        try:
            raw_bits = bit_unstuff(stuffed)
            if len(raw_bits) % 8 == 0:
                frames.append(lsb_bits_to_bytes(raw_bits))
        except ValueError:
            continue
    return frames
