from flask import Flask, render_template, request, jsonify
from engine import create_evaluator

app = Flask(__name__)

# Create a centralized evaluator
evaluator = create_evaluator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.get_json()
    expression = data.get('expression', '')

    if not expression:
        return jsonify({'error': 'Invalid expression'}), 400

    try:
        # Clear previous errors, as the interpreter is reused
        evaluator.error = []
        result = evaluator.eval(expression)

        # Check if any errors occurred during evaluation
        if evaluator.error:
            # Get the first error and format it
            error_message = evaluator.error[0].get_error()[1]
            return jsonify({'error': error_message}), 400

        return jsonify({'result': result})
    except Exception as e:
        # This will catch other unexpected errors
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)