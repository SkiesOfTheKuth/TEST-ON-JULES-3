document.addEventListener('DOMContentLoaded', () => {
    const display = document.getElementById('display');
    const buttons = document.querySelector('.buttons');
    let currentExpression = '';
    let isResultDisplayed = false;

    buttons.addEventListener('click', (e) => {
        if (!e.target.matches('.btn')) return;

        const button = e.target;
        const value = button.dataset.value;
        const isOperator = button.classList.contains('operator');

        if (value === 'C') {
            currentExpression = '';
            display.textContent = '0';
            isResultDisplayed = false;
        } else if (value === '=') {
            if (currentExpression === '') return;
            calculate(currentExpression);
        } else {
            if (isResultDisplayed) {
                if (isOperator) {
                    // Continue calculation with the result
                    isResultDisplayed = false;
                } else {
                    // Start a new calculation
                    currentExpression = '';
                    isResultDisplayed = false;
                }
            }
            currentExpression += value;
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
                const result = data.result;
                // Format result to avoid long decimals
                const formattedResult = Number.isInteger(result) ? result : parseFloat(result.toFixed(10));
                display.textContent = formattedResult;
                currentExpression = String(formattedResult);
                isResultDisplayed = true;
            } else {
                display.textContent = 'Error';
                currentExpression = '';
                isResultDisplayed = false;
            }
        } catch (error) {
            display.textContent = 'Error';
            currentExpression = '';
            isResultDisplayed = false;
        }
    }
});