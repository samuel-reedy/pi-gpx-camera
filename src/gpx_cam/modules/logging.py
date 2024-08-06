import logging

class ExcludeSpecificLogFilter(logging.Filter):
    def filter(self, record):
        # Exclude log messages containing specific text
        if '304 GET /settings' in record.getMessage():
            return False
        return True

# Configure the logging settings
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create a logger instance
logger = logging.getLogger(__name__)

# Add the custom filter to the logger
logger.addFilter(ExcludeSpecificLogFilter())