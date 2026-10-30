# PetSafe Control for Home Assistant

Feed your pets and watch their feeders from Home Assistant, and let assistants (Claude through Home Assistant's MCP server, or Assist) feed them by name: "feed the dogs", "feed Shiloh a half cup". PetSafe Smart Feed feeders and ScoopFree litter boxes, through PetSafe's cloud, as PetSafe's apps reach them.

## Supported devices

- **Smart Feed** feeders, first and second generation (any number of them).
- **ScoopFree** self-cleaning litter boxes.

## Installation

### HACS
1. If the original PetSafe integration (dcmeglio's `homeassistant-petsafe`) is installed, remove it in HACS first: both install to `custom_components/petsafe`. Its sign-in, devices and entities carry over to this one.
2. Go to HACS → Integrations → ⋮ → Custom repositories, and add this repository's URL as an Integration.
3. Download **PetSafe Control**, then restart Home Assistant.
4. If it isn't set up yet: **Settings → Devices & services → Add integration → PetSafe Control**.

### Signing in
Enter your PetSafe account's email; PetSafe emails a code, which you enter next. Home Assistant keeps the sign-in's tokens, not a password (PetSafe accounts have none). Then choose the feeders and litter boxes to add.

### Removal
1. Go to **Settings → Devices & services → PetSafe Control**, open the ⋮ menu, and choose **Delete**.
2. To remove the code too, remove the integration in HACS and restart Home Assistant.

## What you can do

1. **Feed now**, a feeder's usual portion (its Feed button) or any amount (the `petsafe.feed` action).
2. **Let assistants feed your pets** by name, their portion or a snack (see [Assistants](#assistants)).
3. **Watch the food**: how full each feeder is, when it last fed and when it feeds next.
4. **Change a feeder's settings and schedules**: pause its schedules, lock its button, slow feeding; add, change or remove scheduled feedings.
5. **Rake a litter box**, and follow its raking.

## Entities

Each **feeder** has:

| Entity | What it does |
| --- | --- |
| Feed (button) | Feeds the feeder's portion now |
| Portion (number, cups) | The feeder's usual feeding, in eighths of a cup up to 4: what Feed, `petsafe.feed` without an amount, and assistants without cups give. PetSafe keeps no such setting (the app's amount stays in the app), so Home Assistant keeps it; it starts at what the feeder last gave |
| Food Level | full, low or empty |
| Last Feeding | When the feeder last fed |
| Next Feeding | Its next scheduled feeding, in the feeder's timezone; unknown without schedules or while they're paused |
| Battery Level | The batteries' charge; unknown on the adapter without batteries |
| Signal Strength | Wi-Fi signal (diagnostic) |
| Feeding Paused, Child Lock, Slow Feed (switches) | The feeder's settings |

Each **litter box** has Clean and Reset buttons, a Rake Timer (minutes after a cat leaves), and Rake Counter, Rake Status (idle, timing, raking or jammed), Last Cleaning and Signal Strength sensors.

## Actions

Every action targets feeders by entity, device, area, floor or label.

| Action | What it does |
| --- | --- |
| `petsafe.feed` | Feeds now: `amount` (eighths of a cup, 1-32) or `cups` (1/8 to 4), else the feeder's portion; `slow_feed` overrides the feeder's setting |
| `petsafe.prime` | Feeds 5/8 cup to fill the chute |
| `petsafe.add_schedule` | Adds a daily feeding: `time`, `amount` (eighths) |
| `petsafe.modify_schedule` | Changes the amount of the daily feeding at `time` |
| `petsafe.delete_schedule` | Removes the daily feeding at `time` |
| `petsafe.delete_all_schedules` | Removes every daily feeding |

## Assistants

The integration offers assistants one tool, **FeedPet**: a pet's name (as its feeder is named: "Eva Feeder" feeds Eva) or `all`, and optionally cups. Without cups, each pet gets its portion; with them, that feeding only, which leaves the portion as it was. An amount a feeder can't give (under 1/8 or over 4 cups) is refused.

It's served as Home Assistant's **PetSafe Control** LLM API: an MCP server set to serve all LLM APIs offers it to Claude as `petsafe_control__FeedPet`; a conversation agent offers it when PetSafe Control is among its APIs.

## Developing

A Python project managed with [uv](https://docs.astral.sh/uv/); everything runs through `./flow` (the [flows](../../cellular/flows) task runner):

| Command | What it does |
| --- | --- |
| `flow test` | Runs the pytest suite under `test/` through uv, against a fake PetSafe cloud |
| `flow lint` | Lints the integration and its tests with ruff |

`custom_components/petsafe/petsafe_api/` is the [petsafe](https://github.com/dcmeglio/petsafe) library (2.0.6, MIT), carried in the integration, with fixes: tokens are refreshed when they expire (not before every request), the last feeding is the newest, and repeating it reads its amount.

Changes go through flows' branch workflow (`flow branch`, `flow commit`, `flow promote`, `flow merge`). Every pushed branch is tested in castle's CI, and `main` only merges a green Pull Request. castle's Forgejo is the source; GitHub is its push mirror, which HACS installs from.

## Credits

Taken over from Dominick Meglio's [homeassistant-petsafe](https://github.com/dcmeglio/homeassistant-petsafe) (1.4.0), with its contributors cmccambridge, hanscats, ireneybean and seganku, and the [petsafe](https://github.com/dcmeglio/petsafe) library by Jordan Stremming and Dominick Meglio.
