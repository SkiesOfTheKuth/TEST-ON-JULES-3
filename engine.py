import asteval
from logic import Calculator

def create_evaluator():
    """
    Creates and configures an asteval.Interpreter instance.

    This function initializes an asteval interpreter and populates its symbol
    table with the required mathematical functions from the `Calculator` class.
    This centralized evaluator can be used across different frontends
    (web, CLI, GUI) to ensure consistent behavior.

    Returns:
        asteval.Interpreter: A configured asteval interpreter instance.
    """
    evaluator = asteval.Interpreter()
    calculator = Calculator()
    evaluator.symtable.update({
        'sqrt': calculator.sqrt,
        'power': calculator.power,
        'sin': calculator.sin,
        'cos': calculator.cos,
        'tan': calculator.tan,
        'asin': calculator.asin,
        'acos': calculator.acos,
        'atan': calculator.atan,
        'log': calculator.log,
        'log10': calculator.log10,
        'factorial': calculator.factorial,
        'percentage': calculator.percentage,
        'mod': calculator.mod,
        'pi': calculator.pi,
        'e': calculator.e,
    })
    return evaluator