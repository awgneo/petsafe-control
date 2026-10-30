"""Constants for the PetSafe integration."""

DOMAIN = "petsafe"
CONF_REFRESH_TOKEN = "refresh_token"
MANUFACTURER = "PetSafe"
FEEDER_MODEL_GEN1 = "SmartFeed_1.0"
FEEDER_MODEL_GEN2 = "SmartFeed_2.0"

SERVICE_ADD_SCHEDULE = "add_schedule"
SERVICE_DELETE_SCHEDULE = "delete_schedule"
SERVICE_DELETE_ALL_SCHEDULES = "delete_all_schedules"
SERVICE_MODIFY_SCHEDULE = "modify_schedule"
SERVICE_FEED = "feed"
SERVICE_PRIME = "prime"

ATTR_TIME = "time"
ATTR_AMOUNT = "amount"
ATTR_CUPS = "cups"
ATTR_SLOW_FEED = "slow_feed"

# A feeder measures food in eighths of a cup, from one eighth to four cups a feeding
EIGHTHS_PER_CUP = 8
MIN_EIGHTHS = 1
MAX_EIGHTHS = 32
# Priming fills the feeder's chute: 5/8 cup
PRIME_EIGHTHS = 5

RAKE_FINISHED = "RAKE_FINISHED"
CAT_IN_BOX = "CAT_IN_BOX"
ERROR_SENSOR_BLOCKED = "ERROR_SENSOR_BLOCKED"
RAKE_BUTTON_DETECTED = "RAKE_BUTTON_DETECTED"
RAKE_NOW = "RAKE_NOW"
RAKE_COUNTER_RESET = "RAKE_COUNTER_RESET"

FEED_DONE = "FEED_DONE"
