# Firtigh - AI-powered Telegram Bot

Firtigh is a Telegram bot that uses AI to generate responses when mentioned in a group chat.

## Features

- Responds to mentions (`@@firtigh`) in group chats
- Generates AI-powered responses using OpenAI's GPT model
- Easy to deploy and configure

## Prerequisites

- Python 3.8 or higher
- A Telegram account
- An OpenAI API key

## Setup

### 1. Clone this repository

```bash
git clone https://github.com/yourusername/firtigh.git
cd firtigh
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create a Telegram bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Start a chat with BotFather by clicking "Start"
3. Send `/newbot` to create a new bot
4. Follow the instructions to name your bot (e.g., "Firtigh")
5. Choose a username for your bot (must end with "bot", e.g., "firtighbot")
6. BotFather will provide a token - save this token for later

### 4. Configure environment variables

1. Create a `.env` file based on the provided `.env.example`:

```bash
cp .env.example .env
```

2. Open the `.env` file and replace the placeholder values:
   - `TELEGRAM_TOKEN`: The token you received from BotFather
   - `OPENAI_API_KEY`: Your OpenAI API key (get one from [OpenAI's website](https://platform.openai.com/account/api-keys))

## Running the Bot

### Local Deployment

Run the bot locally with:

```bash
python bot.py
```

The bot will continue running until you stop the process.

### Production Deployment

For production deployment, you can use a service like Heroku, AWS, or DigitalOcean:

#### Heroku Deployment

1. Install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
2. Log in to Heroku:

```bash
heroku login
```

3. Create a new Heroku app:

```bash
heroku create firtigh-bot
```

4. Add a `Procfile` to the repository:

```
worker: python bot.py
```

5. Set environment variables:

```bash
heroku config:set TELEGRAM_TOKEN=your_telegram_bot_token
heroku config:set OPENAI_API_KEY=your_openai_api_key
```

6. Deploy to Heroku:

```bash
git push heroku main
```

7. Start the worker:

```bash
heroku ps:scale worker=1
```

## Adding the Bot to a Group

1. Open Telegram and find your bot by username
2. Start a chat with the bot by clicking "Start"
3. Create a new group or open an existing group
4. Add the bot to the group by clicking the group name, then "Add member", and search for your bot

## Using the Bot

1. In a group where the bot is a member, simply mention the bot with `@@firtigh` followed by your query
2. For example: "@@firtigh What's the weather like today?"
3. The bot will process your message and reply with an AI-generated response

## Commands

- `/start` - Introduces the bot and explains how to use it
- `/help` - Shows a help message

## Customization

You can customize the bot's AI responses by modifying the `generate_ai_response` function in `bot.py`. You can change the model, temperature, and other parameters to adjust the AI's behavior.

## Troubleshooting

- If the bot is not responding, make sure it has been added to the group correctly
- Verify that your environment variables are set correctly
- Check the logs for any error messages

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Running Tests

This project includes a comprehensive test suite to ensure the bot functions correctly. The tests are available in two formats: pytest-based and unittest-based.

### Prerequisites

Before running tests, make sure you have installed all the dependencies:

```bash
pip install -r requirements.txt
```

### Running with pytest

To run the pytest-based tests, use one of the following commands from the project root directory:

```bash
# Run all tests with pytest
pytest

# Run tests with verbose output
pytest -v

# Run a specific test file
pytest tests/test_bot_integration.py

# Run a specific test function
pytest tests/test_bot_integration.py::test_start_command
```

Alternatively, you can use the convenience script:

```bash
python run_tests.py
```

#### Running with unittest

If you prefer the unittest framework or have issues with pytest, you can use the unittest-based tests:

```bash
# Run all tests with unittest
python -m unittest discover tests

# Run a specific test file
python -m unittest tests/test_bot_unittest.py
```

Or use the convenience script:

```bash
python run_unittest_tests.py
```

### Test Coverage

The tests cover the following functionality:

1. Command handlers (/start, /help)
2. Message handling with and without bot mentions
3. AI response generation with both success and error cases

### Adding More Tests

To add more tests, create new test functions in the existing test files or add new test files in the `tests` directory. Make sure test files start with `test_` and test functions start with `test_`.

### Verifying Tests Without Running

If you're unable to run the tests directly due to environment constraints, you can still verify the test code through a review:

1. Check the test structure and organization
   - Tests are organized in the `tests` directory
   - There are two test files: `test_bot_integration.py` (pytest-based) and `test_bot_unittest.py` (unittest-based)

2. Verify test coverage
   - All main functions in `bot.py` have corresponding test functions
   - Tests include positive and negative cases
   - Edge cases are considered

3. Verify test quality
   - Tests use proper mocking of external dependencies (Telegram, OpenAI)
   - Assertions are meaningful and focused
   - Test functions are well-documented

4. When you're ready to run the tests in your development environment, follow the instructions above. 