"""Deterministic data for the two additional 1022 problems."""
import itertools
import random
import string

COLOR_MASKS = (1, 2, 4, 3, 6, 0, 5)


def colors(n, intervals):
    """Count constant-color segments between all endpoints."""
    edges = sorted({1, n + 1, *(x for l, r in intervals for x in (l, r + 1))})
    counts = [0] * 8
    for left, right in zip(edges, edges[1:]):
        mask = sum(1 << i for i, (l, r) in enumerate(intervals) if l <= left <= r)
        counts[mask] += right - left
    counts[0] += counts[7]
    return ' '.join(str(counts[m]) for m in COLOR_MASKS)


def colors_bruteforce(n, intervals):
    walls = [0] * n
    for bit, (left, right) in enumerate(intervals):
        for pos in range(left - 1, right):
            walls[pos] |= 1 << bit
    counts = [walls.count(mask) for mask in range(8)]
    counts[0] += counts[7]
    return ' '.join(str(counts[m]) for m in COLOR_MASKS)


def decrypt(text):
    table = str.maketrans(string.ascii_lowercase + string.ascii_uppercase,
                         string.ascii_uppercase + string.ascii_uppercase[1:] + 'A')
    return text.translate(table)


def extra_cases():
    rng = random.Random(102203)
    # Exhaust all three intervals on small walls, including endpoints and triple overlaps.
    for n in range(1, 5):
        ranges = [(l, r) for l in range(1, n + 1) for r in range(l, n + 1)]
        for intervals in itertools.product(ranges, repeat=3):
            assert colors(n, intervals) == colors_bruteforce(n, intervals)
    color_inputs = [
        (10, [(1, 4), (3, 6), (5, 8)]),
        (5, [(2, 4), (2, 4), (2, 4)]),
        (8, [(1, 4), (6, 8), (3, 6)]),
        (1, [(1, 1)] * 3), (3, [(1, 1), (2, 2), (3, 3)]),
        (7, [(1, 5), (3, 7), (2, 6)]),
        (10, [(1, 10), (3, 8), (5, 6)]),
        (999999, [(1, 999999)] * 3),
        (999999, [(1, 1), (999999, 999999), (500000, 500000)]),
        (999999, [(1, 700000), (300000, 999999), (100000, 800000)]),
    ]
    for _ in range(12):
        n = rng.randint(2, 300)
        intervals = [tuple(sorted((rng.randint(1, n), rng.randint(1, n)))) for _ in range(3)]
        assert colors(n, intervals) == colors_bruteforce(n, intervals)
        color_inputs.append((n, intervals))
    color_cases = [{'input': str(n) + '\n' + ''.join(f'{l} {r}\n' for l, r in intervals),
                    'expected_output': colors(n, intervals) + '\n'} for n, intervals in color_inputs]
    texts = ['aAzZ', 'HelloWorld', 'xyzXYZ', 'a', 'Z', 'z', 'A',
             string.ascii_lowercase, string.ascii_uppercase,
             ''.join(a + b for a, b in zip(string.ascii_lowercase, string.ascii_uppercase)),
             'Az' * 1000, 'Z' * 65535, 'z' * 65536, 'aAZz' * 16384 + 'Z',
             ''.join(rng.choices(string.ascii_letters, k=999999))]
    cipher_cases = []
    for text in texts:
        independent = ''.join(c.upper() if c.islower() else chr((ord(c) - 65 + 1) % 26 + 65) for c in text)
        assert decrypt(text) == independent
        cipher_cases.append({'input': text + '\n', 'expected_output': independent + '\n'})
    return color_cases, cipher_cases
