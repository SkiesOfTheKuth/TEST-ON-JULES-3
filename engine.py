import asteval
import logic

def create_evaluator():
    """
    Creates and configures an asteval.Interpreter instance.

    This function initializes an asteval interpreter and populates its symbol
    table with the required mathematical functions from the `logic` module.
    This centralized evaluator can be used across different frontends
    (web, CLI, GUI) to ensure consistent behavior.

    Returns:
        asteval.Interpreter: A configured asteval interpreter instance.
    """
    evaluator = asteval.Interpreter()
    evaluator.symtable.update({
        'sqrt': logic.sqrt,
        'power': logic.power,
        'sin': logic.sin,
        'cos': logic.cos,
        'tan': logic.tan,
        'log': logic.log,
        'log10': logic.log10,
        'factorial': logic.factorial,
        'percentage': logic.percentage,
    })
    return evaluator