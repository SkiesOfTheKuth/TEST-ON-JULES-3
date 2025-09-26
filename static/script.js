document.addEventListener('DOMContentLoaded', () => {
    const display = document.getElementById('display');
    const buttons = document.querySelector('.buttons');
    let currentExpression = '';
    let isResultDisplayed = false;

    buttons.addEventListener('click', (e) => {
        if (!e.target.matches('.btn')) return;

        const value = e.target.dataset.value;

        if (value === 'C') {
            currentExpression = '';
            display.textContent = '0';
            isResultDisplayed = false;
        } else if (value === '=') {
            if (currentExpression === '') return;
            calculate(currentExpression);
        } else {
            if (isResultDisplayed) {
                const operators = ['+', '-', '*', '/', '**'];
                if (operators.includes(value)) {
                    // If an operator is pressed, continue with the result
                } else if (value === '(' && currentExpression.slice(-1) === ')') {
                    // If the result is a function call, start a new expression
                    currentExpression = '';
                }
                else {
                    // Otherwise, start a new expression
                    currentExpression = '';
                }
                isResultDisplayed = false;
            }

            if (display.textContent === '0' && value !== '.') {
                currentExpression = value;
            } else {
                currentExpression += value;
            }
            display.textContent = currentExpression;
        }
    });

    async function calculate(expression) {
        try {
            const response = await fetch('/calculate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ expression: expression }),
            });

            const data = await response.json();

            if (response.ok) {
                display.textContent = data.result;
                currentExpression = String(data.result);
                isResultDisplayed = true;
            } else {
                display.textContent = 'Error';
                currentExpression = '';
            }
        } catch (error) {
            display.textContent = 'Error';
            currentExpression = '';
        }
    }
});