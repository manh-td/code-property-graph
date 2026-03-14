from examples.functions import example_function

def greet(name: str) -> str:
    return f"Hello, {name}!"


def main() -> None:
    print(greet("joern"))


if __name__ == "__main__":
    example_function()
    main()
