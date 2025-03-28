# فیرتیق - Enhanced Telegram Bot

فیرتیق (Firtigh) is an intelligent Telegram bot designed to interact with group members in a natural, conversational way.

## Key Features

### Intelligence and Personality

- **Advanced AI Model**: Uses O3 mini model for all responses to provide high-quality interactions
- **Persian First**: Always responds in Persian language
- **Fun, Informal Personality**: Has a sarcastic, fun personality with no filtering of language
- **Can Argue and Debate**: Capable of contradicting users if it thinks they're wrong

### Activation

- Responds when mentioned by name "فیرتیق" or "firtigh"
- Responds when mentioned with "@firtigh"
- Responds when someone replies to its messages

### Memory and Context

- **Enhanced Group Memory**: Remembers up to 1000 recent messages from the group
- **Topic Tracking**: Organizes memories by topic for better context in responses
- **User Profiling**: Creates profiles of users based on:
  - Personality traits
  - Topics of interest
  - Writing style and tone
  - Sentiment patterns
  - Message frequency
- **Name Correction**: Learns to use proper Persian names for users when corrected

### Information Tools

- **Web Search**: Can search the web for real-time information
- **Link Analysis**: Extracts and summarizes content from shared links
- **News Aggregation**: Can compile news from top Persian news sites
- **Weather Information**: Can retrieve weather information
- **Image Understanding**: Can analyze and understand images and animated GIFs

### Conversation Management

- **Thread Context**: Understands context in reply threads
- **Instruction Following**: Can accept and remember instructions from users
- **Markdown Formatting**: Uses proper formatting for better readability
- **Function Calling**: Uses OpenAI's function calling to determine when to search the web or extract content

## Technical Details

- The memory system stores both factual information and conversational context
- User profiles are built incrementally through natural interaction
- Enhanced name correction system that learns the proper Persian spelling of users' names
- Response formatting is optimized for Telegram, including proper links and markdown
- High-quality error handling to ensure stability
- Persian-first interaction design

## Usage Examples

- **Simple Chat**: "@firtigh خوبی؟" (How are you?)
- **Web Search**: "@firtigh جستجو کن قیمت طلا" (Search for gold prices)
- **Group Memory**: "@firtigh خلاصه گفتگوهای سه روز اخیر" (Summarize conversations from the last three days)
- **News**: "@firtigh اخبار امروز چیه؟" (What's the news today?)
- **Image Analysis**: Reply to an image with "@firtigh این چیه؟" (What is this?)
- **Instructions**: "@firtigh از این به بعد من رو علی صدا کن" (From now on call me Ali)
- **Discussions**: Can join and participate in group discussions naturally

## Authors

فیرتیق الله باقرزاده (Firtigh Allah Bagherzadeh) - AI Telegram Bot

## Features

- Responds to mentions (`@@firtigh`) in group chats
- Generates AI-powered responses using OpenAI's GPT model
- Summarizes chat history from group discussions
- Searches the web for real-time information
- Prioritizes Persian news sources for news-related queries
- Extracts and analyzes content from shared links
- Processes and analyzes images and GIFs
- Uses Persian language with customizable personality
- Maintains strict isolation between different chat groups
- Enforces configurable usage limits for search and media
- Easy to deploy and configure on multiple platforms

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
   - `GOOGLE_API_KEY`: (Optional) For web search functionality (get from [Google Cloud Console](https://console.cloud.google.com/))
   - `GOOGLE_SEARCH_ENGINE_ID`: (Optional) For web search functionality (create at [Programmable Search Engine](https://programmablesearchengine.google.com/))
   - `DAILY_SEARCH_LIMIT`: Maximum number of web searches per day (default: 50)
   - `DAILY_MEDIA_LIMIT`: Maximum number of image/video analyses per day (default: 10)

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

##### Using Bash (Linux/Mac)

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

5. Set environment variables using the provided script:

```bash
# Make sure the script is executable
chmod +x update_heroku_config.sh

# Run the script
./update_heroku_config.sh
```

6. Deploy to Heroku with the included script:

```bash
./deploy.sh "Initial deployment"
```

7. Start the worker:

```bash
heroku ps:scale worker=1
```

##### Using PowerShell (Windows)

1. Install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
2. Log in to Heroku:

```powershell
heroku login
```

3. Create a new Heroku app:

```powershell
heroku create firtigh-bot
```

4. Add a `Procfile` to the repository:

```
worker: python bot.py
```

5. Set environment variables using the provided script:

```powershell
# Run the script
.\update_heroku_config.ps1
```

6. Deploy to Heroku with the included script:

```powershell
.\deploy.ps1 -CommitMessage "Initial deployment"
```

7. Start the worker:

```powershell
heroku ps:scale worker=1
```

## Monitoring and Logs

### Viewing Heroku Logs
To monitor your bot and troubleshoot issues, you can view the application logs from Heroku. Two scripts are provided for easy access to logs:

#### Using PowerShell Script (Windows)
A PowerShell script is available for Windows users:

```powershell
# View live logs (streaming)
.\view_logs.ps1 -Tail

# View most recent logs (default: 100 lines)
.\view_logs.ps1

# View specific number of lines
.\view_logs.ps1 -Lines 200

# Filter logs by source (application only)
.\view_logs.ps1 -Source app

# Display help
.\view_logs.ps1 -Help
```

#### Using Bash Script (Linux/Mac)
For Linux and Mac users, use the Bash script:

```bash
# Make the script executable (first time only)
chmod +x view_logs.sh

# View live logs (streaming)
./view_logs.sh --tail

# View most recent logs (default: 100 lines)
./view_logs.sh

# View specific number of lines
./view_logs.sh --lines 200

# Filter logs by source (application only)
./view_logs.sh --source app

# Display help
./view_logs.sh --help
```

#### Direct Heroku CLI Commands
You can also use the Heroku CLI directly:

```bash
# Stream live logs
heroku logs --tail --app your-app-name

# View most recent logs
heroku logs --app your-app-name

# View specific number of lines
heroku logs -n 200 --app your-app-name
```

### Log Interpretation
Important log entries to look for:
- Bot startup confirmation
- Command processing
- Error messages
- Memory and database operations

## Adding the Bot to a Group

1. Open Telegram and find your bot by username
2. Start a chat with the bot by clicking "Start"
3. Create a new group or open an existing group
4. Add the bot to the group by clicking the group name, then "Add member", and search for your bot

## Using the Bot

1. In a group where the bot is a member, simply mention the bot with `@@firtigh` followed by your query
2. For example: "@@firtigh What's the weather like today?"
3. The bot will process your message and reply with an AI-generated response

### Special Features

- **Chat History Summarization**: Ask the bot to summarize recent group conversations
  - Example: "@@firtigh خلاصه گفتگوهای سه روز اخیر چیه؟" (What's the summary of discussions in the last three days?)
  - Supports different time periods (1 day, 3 days, 1 week, etc.)

- **Web Search**: Ask the bot to search the internet for information
  - Example: "@@firtigh جستجو کن آخرین اخبار ایران" (Search for the latest news about Iran)
  - Use keywords like "جستجو", "search", "سرچ", or "گوگل" to trigger a search
  - Daily search limits prevent excessive usage

- **Persian News Prioritization**: When asking about news, the bot prioritizes Persian news sources
  - Example: "@@firtigh اخبار امروز چیه؟" (What's today's news?)
  - Sources include BBC Persian, Euronews Persian, Iran International, and more

- **Link Analysis**: Send a URL and the bot will extract and analyze its content
  - Example: "@@firtigh نظرت در مورد این مقاله چیه؟ https://example.com/article"
  - Works with most standard websites (may have limitations with JavaScript-heavy sites)

- **Image and GIF Analysis**: Send media with your query and the bot will analyze it
  - Example: Send an image and ask "@@firtigh این عکس چیه؟" (What is this picture?)
  - Daily media processing limits prevent excessive usage
  
- **Usage Limits**: The bot enforces daily limits on resource-intensive operations
  - Web searches and media processing are limited to configurable daily quotas
  - Limits reset every 24 hours
  
- **Group Isolation**: Each group's conversations and memories are completely isolated
  - Information from one group is never leaked to other groups
  - Maintains privacy and context separation between different communities
  
- **Persian Language Support**: The bot is optimized for Persian language interactions
  - Will try to address users by the Persian equivalent of their names

## Commands

- `/start` - Introduces the bot and explains how to use it
- `/help` - Shows a help message

## Customization

You can customize the bot's behavior by modifying the following:

- **AI Personality**: Edit the system message in `generate_ai_response` function
- **Search Settings**: Adjust daily limits in `.env` file
- **Message History**: Control how many messages are stored in `database.py`
- **Language Support**: Improve Persian name handling and responses

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

### Test Coverage

The tests cover the following functionality:

1. Command handlers (/start, /help)
2. Message handling with and without bot mentions
3. AI response generation with both success and error cases
4. Web search and Persian news prioritization
5. Link extraction and content analysis
6. Image processing and analysis
7. Memory and conversation history functionality
8. Usage limits enforcement
9. Group isolation and privacy protection
10. Exchange rate information retrieval

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