from flask import Flask, render_template, request, jsonify
from evaluator import create_evaluator

app = Flask(__name__)

@app.route('/')
def index():
    """Serves the main calculator page."""
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    """
    Evaluates a mathematical expression from a POST request.
    Creates a new, isolated interpreter for each request.
    """
    data = request.get_json(silent=True)
    if not data or 'expression' not in data:
        return jsonify({'error': 'Invalid request format.'}), 400

    expression = data.get('expression', '').strip()
    if not expression:
        return jsonify({'error': 'Expression cannot be empty.'}), 400

    # Create a new interpreter for each request to ensure thread safety and no state leakage.
    evaluator = create_evaluator()

    try:
        # Evaluate the expression
        result = evaluator.eval(expression)

        # Check for internal asteval errors that don't raise exceptions
        if evaluator.error:
            error_message = evaluator.error[0].get_error()[1]
            return jsonify({'error': error_message}), 400

        return jsonify({'result': result})

    except Exception as e:
        # Catches exceptions from custom logic (e.g., ValueError) and other runtime errors.
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    # Use threaded=True for better performance with multiple requests
    app.run(debug=True, threaded=True)