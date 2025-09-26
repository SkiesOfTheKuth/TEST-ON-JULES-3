document.addEventListener('DOMContentLoaded', () => {
    const display = document.getElementById('display');
    const buttons = document.querySelector('.buttons');
    const historyList = document.getElementById('history-list');
    const clearHistoryBtn = document.getElementById('clear-history');

    let currentExpression = '';
    let isResultDisplayed = false;

    // Load history from local storage
    loadHistory();

    buttons.addEventListener('click', (e) => {
        if (!e.target.matches('.btn')) return;

        const value = e.target.dataset.value;

        if (value === 'C') {
            currentExpression = '';
            display.value = '';
            isResultDisplayed = false;
        } else if (value === '=') {
            if (currentExpression === '') return;
            calculate(currentExpression);
        } else {
            if (isResultDisplayed) {
                const operators = ['+', '-', '*', '/', '**'];
                if (operators.includes(value)) {
                    // Continue with the result
                } else {
                    // Start a new expression
                    currentExpression = '';
                }
                isResultDisplayed = false;
            }
            currentExpression += value;
            display.value = currentExpression;
        }
    });

    clearHistoryBtn.addEventListener('click', () => {
        clearHistory();
    });

    historyList.addEventListener('click', (e) => {
        const item = e.target.closest('.list-group-item');
        if (!item) return;

        const expression = item.dataset.expression;
        if (expression) {
            currentExpression = expression;
            display.value = currentExpression;
            isResultDisplayed = false;
        }
    });

    async function calculate(expression) {
        try {
            const response = await fetch('/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ expression: expression }),
            });

            const data = await response.json();

            if (response.ok) {
                display.value = data.result;
                addToHistory(expression, data.result);
                currentExpression = String(data.result);
                isResultDisplayed = true;
            } else {
                display.value = 'Error';
                currentExpression = '';
            }
        } catch (error) {
            display.value = 'Error';
            currentExpression = '';
        }
    }

    function addToHistory(expression, result) {
        const history = getHistory();
        history.unshift({ expression, result });
        if (history.length > 20) { // Keep last 20 calculations
            history.pop();
        }
        localStorage.setItem('calculatorHistory', JSON.stringify(history));
        renderHistory();
    }

    function getHistory() {
        return JSON.parse(localStorage.getItem('calculatorHistory')) || [];
    }

    function renderHistory() {
        const history = getHistory();
        historyList.innerHTML = '';
        history.forEach(item => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.dataset.expression = item.expression;
            li.innerHTML = `
                <div class="expression">${item.expression} =</div>
                <div class="result">${item.result}</div>
            `;
            historyList.appendChild(li);
        });
    }

    function loadHistory() {
        renderHistory();
    }

    function clearHistory() {
        localStorage.removeItem('calculatorHistory');
        renderHistory();
    }
});