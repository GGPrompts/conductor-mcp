# tmux Keybinding Reference

Default prefix: `Ctrl+b` (shown as `C-b` below)

## Session Management

| Keys | Action |
|------|--------|
| `C-b d` | Detach from session |
| `C-b s` | List/switch sessions |
| `C-b $` | Rename session |
| `C-b (` | Previous session |
| `C-b )` | Next session |

## Window (Tab) Management

| Keys | Action |
|------|--------|
| `C-b c` | Create new window |
| `C-b ,` | Rename window |
| `C-b &` | Kill window |
| `C-b n` | Next window |
| `C-b p` | Previous window |
| `C-b 0-9` | Go to window by number |
| `C-b w` | List/choose window |
| `C-b l` | Last active window |

## Pane Navigation

| Keys | Action |
|------|--------|
| `C-b %` | Split horizontal (side by side) |
| `C-b "` | Split vertical (stacked) |
| `C-b o` | Cycle to next pane |
| `C-b ;` | Toggle last active pane |
| `C-b Arrow` | Move to pane by direction |
| `C-b q` | Show pane numbers (press number to jump) |
| `C-b x` | Kill current pane |
| `C-b z` | Toggle pane zoom (fullscreen) |
| `C-b {` | Swap pane left/up |
| `C-b }` | Swap pane right/down |
| `C-b !` | Break pane into own window |

## Pane Resizing

| Keys | Action |
|------|--------|
| `C-b C-Arrow` | Resize pane (1 cell) |
| `C-b M-Arrow` | Resize pane (5 cells) |
| `C-b Space` | Cycle through layouts |
| `C-b M-1` | Even horizontal layout |
| `C-b M-2` | Even vertical layout |
| `C-b M-3` | Main horizontal layout |
| `C-b M-4` | Main vertical layout |
| `C-b M-5` | Tiled layout |

## Copy Mode (scroll/search)

| Keys | Action |
|------|--------|
| `C-b [` | Enter copy mode |
| `q` | Exit copy mode |
| `Up/Down` | Scroll line by line |
| `PgUp/PgDn` | Scroll by page |
| `/` | Search forward |
| `?` | Search backward |
| `n` | Next search match |
| `N` | Previous search match |
| `Space` | Start selection |
| `Enter` | Copy selection |

## Miscellaneous

| Keys | Action |
|------|--------|
| `C-b :` | Command prompt |
| `C-b t` | Show clock |
| `C-b ?` | List all keybindings |
| `C-b ~` | Show messages |
