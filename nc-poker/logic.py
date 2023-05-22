from random import randint


def get_random_hand(n: int, lb: int = 1, ub: int = 15) -> tuple[int, int, int]:
    """Get n random ints in the range lb..ub inclusive"""
    assert (ub - lb + 1) >= n, "Pigeon-holed!"

    numbers = set()

    while len(numbers) < 3:
        numbers.add(randint(lb, ub))

    return tuple(numbers)
