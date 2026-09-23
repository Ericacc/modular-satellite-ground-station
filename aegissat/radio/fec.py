def _parity(value):
    return value.bit_count() & 1


def convolutional_encode(bits, polynomials=(0o7, 0o5), constraint_length=3, terminate=True):
    values = [int(bit) for bit in bits]
    if any(bit not in (0, 1) for bit in values):
        raise ValueError("FEC input must contain only bits")
    if terminate:
        values += [0] * (constraint_length - 1)
    state = 0
    mask = (1 << constraint_length) - 1
    encoded = []
    for bit in values:
        state = ((state << 1) | bit) & mask
        encoded.extend(_parity(state & polynomial) for polynomial in polynomials)
    return encoded


def viterbi_decode(encoded, polynomials=(0o7, 0o5), constraint_length=3, terminated=True):
    symbols = [int(bit) for bit in encoded]
    rate = len(polynomials)
    if len(symbols) % rate:
        raise ValueError("Encoded FEC sequence has an incomplete symbol")
    state_count = 1 << (constraint_length - 1)
    infinite = len(symbols) + 1
    metrics = [infinite] * state_count
    metrics[0] = 0
    paths = [[] for _ in range(state_count)]

    for offset in range(0, len(symbols), rate):
        received = symbols[offset:offset + rate]
        next_metrics = [infinite] * state_count
        next_paths = [[] for _ in range(state_count)]
        for state in range(state_count):
            if metrics[state] == infinite:
                continue
            for bit in (0, 1):
                register = (state << 1) | bit
                expected = [_parity(register & polynomial) for polynomial in polynomials]
                distance = sum(a != b for a, b in zip(received, expected))
                next_state = register & (state_count - 1)
                candidate = metrics[state] + distance
                if candidate < next_metrics[next_state]:
                    next_metrics[next_state] = candidate
                    next_paths[next_state] = paths[state] + [bit]
        metrics, paths = next_metrics, next_paths

    final_state = 0 if terminated else min(range(state_count), key=metrics.__getitem__)
    decoded = paths[final_state]
    if terminated:
        decoded = decoded[:-(constraint_length - 1)]
    return {
        "bits": decoded,
        "corrected_metric": metrics[final_state],
        "decodable": metrics[final_state] < infinite,
    }

