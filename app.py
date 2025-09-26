from flask import Flask, render_template, request, jsonify
import asteval
import logic

app = Flask(__name__)

# Initialize the asteval interpreter
asteval_interpreter = asteval.Interpreter()
asteval_interpreter.symtable.update({
    'sqrt': logic.sqrt,
    'power': logic.power,
})

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
        result = asteval_interpreter.eval(expression)
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)