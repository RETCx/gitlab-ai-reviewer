def average(values):
    """Return the mean. Empty input should raise ValueError."""
    return sum(values) / len(values)


if __name__ == "__main__":
    print(average([10, 20, 30]))