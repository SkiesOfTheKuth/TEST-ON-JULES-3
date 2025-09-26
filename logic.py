import math
from typing import Union

# --- Constants ---
pi = math.pi
e = math.e

# --- Type Alias for numeric types ---
Numeric = Union[int, float]

# --- Basic Arithmetic Operations ---
def add(x: Numeric, y: Numeric) -> Numeric:
    """Adds two numbers."""
    return x + y

def subtract(x: Numeric, y: Numeric) -> Numeric:
    """Subtracts the second number from the first."""
    return x - y

def multiply(x: Numeric, y: Numeric) -> Numeric:
    """Multiplies two numbers."""
    return x * y

def divide(x: Numeric, y: Numeric) -> float:
    """
    Divides the first number by the second.
    Raises a ValueError if the divisor is zero.
    """
    if y == 0:
        raise ValueError("Division by zero is not allowed.")
    return x / y

# --- Exponents and Roots ---
def power(x: Numeric, y: Numeric) -> Numeric:
    """Raises a number to the power of another."""
    return x ** y

def sqrt(x: Numeric) -> float:
    """
    Calculates the square root of a number.
    Raises a ValueError for negative inputs.
    """
    if x < 0:
        raise ValueError("Square root of a negative number is not real.")
    return math.sqrt(x)

# --- Trigonometric Functions (Radians) ---
def sin(x: Numeric) -> float:
    """Calculates the sine of a number in radians."""
    return math.sin(x)

def cos(x: Numeric) -> float:
    """Calculates the cosine of a number in radians."""
    return math.cos(x)

def tan(x: Numeric) -> float:
    """Calculates the tangent of a number in radians."""
    return math.tan(x)

# --- Trigonometric Functions (Degrees) ---
def sind(x: Numeric) -> float:
    """Calculates the sine of a number in degrees."""
    return math.sin(math.radians(x))

def cosd(x: Numeric) -> float:
    """Calculates the cosine of a number in degrees."""
    return math.cos(math.radians(x))

def tand(x: Numeric) -> float:
    """Calculates the tangent of a number in degrees."""
    return math.tan(math.radians(x))

# --- Inverse Trigonometric Functions (Result in Radians) ---
def asin(x: Numeric) -> float:
    """
    Calculates the arc sine of a number.
    Result is in radians.
    Domain: [-1, 1]
    """
    if not -1 <= x <= 1:
        raise ValueError("Arc sine domain is [-1, 1].")
    return math.asin(x)

def acos(x: Numeric) -> float:
    """
    Calculates the arc cosine of a number.
    Result is in radians.
    Domain: [-1, 1]
    """
    if not -1 <= x <= 1:
        raise ValueError("Arc cosine domain is [-1, 1].")
    return math.acos(x)

def atan(x: Numeric) -> float:
    """
    Calculates the arc tangent of a number.
    Result is in radians.
    """
    return math.atan(x)

# --- Logarithmic Functions ---
def log(x: Numeric) -> float:
    """
    Calculates the natural logarithm of a number.
    Raises a ValueError for non-positive inputs.
    """
    if x <= 0:
        raise ValueError("Logarithm is undefined for non-positive numbers.")
    return math.log(x)

def log10(x: Numeric) -> float:
    """
    Calculates the base-10 logarithm of a number.
    Raises a ValueError for non-positive inputs.
    """
    if x <= 0:
        raise ValueError("Logarithm is undefined for non-positive numbers.")
    return math.log10(x)

# --- Factorial ---
def factorial(x: int) -> int:
    """
    Calculates the factorial of a non-negative integer.
    Raises a ValueError for negative numbers or non-integers.
    """
    if not isinstance(x, int) or x < 0:
        raise ValueError("Factorial is only defined for non-negative integers.")
    return math.factorial(x)

# --- Hyperbolic Functions ---
def sinh(x: Numeric) -> float:
    """Calculates the hyperbolic sine of a number."""
    return math.sinh(x)

def cosh(x: Numeric) -> float:
    """Calculates the hyperbolic cosine of a number."""
    return math.cosh(x)

def tanh(x: Numeric) -> float:
    """Calculates the hyperbolic tangent of a number."""
    return math.tanh(x)