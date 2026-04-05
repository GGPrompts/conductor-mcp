package main

// types.go - Type Definitions
// Purpose: All type definitions, structs, enums, and constants
// When to extend: Add new types here when introducing new data structures

// Focus state constants for adaptive 3-panel layout
const (
	FocusSessions = 0 // Sessions list (top panel)
	FocusPreview  = 1 // Preview pane (middle panel)
	FocusCommand  = 2 // Command input (bottom panel)
)

// Model represents the application state
type model struct {
	// Configuration
	config Config

	// UI State
	width  int
	height int

	// Focus management
	focusedComponent string

	// Error handling
	err       error
	statusMsg string

	// Post-exit actions
	attachOnExit string // Session name to attach to after TUI exits
	popupMode    bool   // Running in tmux popup mode (switch instead of attach)
	watcherMode  bool   // Running in watcher mode (sessions-only view, no preview/command)

	// Tmux data
	sessions           []TmuxSession
	selectedSession    int    // Index of selected session in left panel
	currentSessionName string // Name of the session we're currently in (empty if not in tmux)

	// Template data
	templates        []SessionTemplate // Available templates
	selectedTemplate int               // Index of selected template in right panel

	// Tree view for categorized templates (right panel)
	expandedCategories map[string]bool     // Category name -> expanded state
	templateTreeItems  []TemplateTreeItem  // Flattened tree items for rendering

	// Tree view for sessions (left panel - Phase 10.5: Session Tree)
	expandedSessions map[string]bool    // Session name -> expanded state
	sessionTreeItems []SessionTreeItem  // Flattened tree items for rendering
	sessionFilter    string             // Filter: "all", "ai", "attached", "detached"

	// Window navigation (for Phase 4: Preview Panel)
	windows        []TmuxWindow // Windows for currently selected session
	selectedWindow int          // Index of selected window for preview

	// Preview scrolling (for Phase 6: Scrollable Preview)
	previewBuffer     []string // Full pane content buffer
	previewScrollOffset int    // Current scroll position (line offset)
	previewTotalLines int      // Total lines in buffer

	// Sessions panel scrolling
	sessionsScrollOffset int // Current scroll position for sessions list

	// Focus state for 3-panel layout
	focusState int // Current focus: FocusSessions (0), FocusPreview (1), FocusCommand (2)

	// Tab state for top panel (Sessions vs Templates)
	sessionsTab string // "sessions" or "templates"

	// Maximize mode - sessions panel takes over preview space
	sessionsMaximized bool // When true, sessions panel uses full height (no preview)

	// Panel content arrays (used by unified view rendering)
	sessionsContent []string // Content for sessions list (top panel)
	previewContent  []string // Content for preview pane (middle panel)
	commandContent  []string // Content for command input (bottom panel, 2-3 lines)
	templatesContent []string // Content for templates (shown on Templates tab if we add it back)

	// Mouse tracking
	mouseX      int
	mouseY      int
	hoveredItem string

	// Input mode for renaming sessions
	inputMode    string // "rename", "template_create", "template_delete_confirm", or empty
	inputBuffer  string // Current input value
	inputPrompt  string // Prompt to show user
	renameTarget string // Session name being renamed

	// Template creation wizard
	templateCreationMode bool
	templateBuilder      TemplateBuilder

	// Session save mode
	sessionSaveMode bool
	sessionBuilder  SessionSaveBuilder

	// Command mode (Phase 9: Unified Chat)
	commandInput    string   // Current command being typed
	commandCursor   int      // Cursor position in command input
	commandHistory  []string // Command history
	historyIndex    int      // Current position in history (-1 = not browsing)
	lastCommand     string   // Last executed command
	lastCommandTime string   // When last command was sent
	lastCommandTarget string // Which session(s) received it

	// Track which session we've auto-scrolled to bottom (to avoid repeating on refresh)
	autoScrolledSession string

	// Footer scrolling (click to activate)
	footerScrolling bool // Whether footer is currently scrolling
	footerOffset    int  // Horizontal scroll offset for footer text
}

// Config holds application configuration
type Config struct {
	// Theme
	Theme       string
	CustomTheme ThemeColors

	// Keybindings
	Keybindings       string
	CustomKeybindings map[string]string

	// Layout
	Layout LayoutConfig

	// UI Elements
	UI UIConfig

	// Performance
	Performance PerformanceConfig

	// Logging
	Logging LogConfig
}

// ThemeColors defines a color theme
type ThemeColors struct {
	Primary    string
	Secondary  string
	Background string
	Foreground string
	Accent     string
	Error      string
}

// LayoutConfig defines layout settings
type LayoutConfig struct {
	Type        string  // single, dual_pane, multi_panel, tabbed
	SplitRatio  float64 // For dual_pane
	ShowDivider bool
}

// UIConfig defines UI element settings
type UIConfig struct {
	ShowTitle       bool
	ShowStatus      bool
	ShowLineNumbers bool
	MouseEnabled    bool
	ShowIcons       bool
	IconSet         string
}

// PerformanceConfig defines performance settings
type PerformanceConfig struct {
	LazyLoading     bool
	CacheSize       int
	AsyncOperations bool
}

// LogConfig defines logging settings
type LogConfig struct {
	Enabled bool
	Level   string
	File    string
}

// Custom message types
// Add your application-specific messages here

type errMsg struct {
	err error
}

type statusMsg struct {
	message string
}

type resizeMsg struct {
	width  int
	height int
}

// Tmux data types

// TmuxSession represents a tmux session
type TmuxSession struct {
	Name        string
	Windows     int
	Attached    bool
	Created     string
	LastActive  string
	WorkingDir  string       // Current working directory of first pane
	GitBranch   string       // Git branch if in a git repo
	ClaudeState *ClaudeState // nil if not a Claude session
	AITool      string       // "claude", "codex", "gemini", or "" for non-AI sessions
}

// TmuxWindow represents a window in a session
type TmuxWindow struct {
	Index  int
	Name   string
	Panes  int
	Active bool
}

// TmuxPane represents a pane in a window
type TmuxPane struct {
	ID      string
	Index   int
	Width   int
	Height  int
	Active  bool
	Command string
}

// Custom message types for async operations
type sessionsLoadedMsg struct {
	sessions []TmuxSession
}

type tickMsg struct{}

type footerTickMsg struct{}

type sessionPreviewMsg struct {
	content string
}

type sessionCreatedMsg struct {
	sessionName string
	err         error
}

type sessionCreatedAndAttachMsg struct {
	sessionName string
	err         error
}

type sessionCreationStartMsg struct {
	templateName string
}

type sessionAttachedMsg struct {
	sessionName string
	err         error
}

type sessionKilledMsg struct {
	sessionName string
	err         error
}

type sessionDetachedMsg struct {
	sessionName string
	err         error
}

type sessionRenamedMsg struct {
	oldName string
	newName string
	err     error
}

type templatesReloadedMsg struct {
	templates []SessionTemplate
	err       error
}

// SessionTemplate represents a template for creating tmux sessions
type SessionTemplate struct {
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Category    string            `json:"category,omitempty"` // Category for organization (e.g., "Projects", "Agents", "Tools")
	WorkingDir  string            `json:"working_dir"`
	Layout      string            `json:"layout"` // "2x2", "4x2", "3x3", etc.
	Panes       []PaneTemplate    `json:"panes"`
	Env         map[string]string `json:"env,omitempty"`
}

// PaneTemplate represents a pane configuration in a template
type PaneTemplate struct {
	Command    string `json:"command"`
	Title      string `json:"title,omitempty"`
	WorkingDir string `json:"working_dir,omitempty"`
}

// TemplateListItem represents an item in the left panel (template or session)
type TemplateListItem struct {
	Type        string // "template" or "session"
	Name        string
	Description string
	Template    *SessionTemplate // Only populated for templates
	Session     *TmuxSession     // Only populated for sessions
}

// TemplateTreeItem represents an item in the categorized tree view (right panel)
type TemplateTreeItem struct {
	Type          string           // "category" or "template"
	Name          string           // Category name or template name
	Category      string           // Category this item belongs to (empty for categories themselves)
	Template      *SessionTemplate // Only populated for templates
	Depth         int              // Indentation level (0 for categories, 1 for templates)
	IsLast        bool             // Is this the last item in its level?
	ParentLasts   []bool           // Track which parent levels are last (for tree connectors)
	TemplateIndex int              // Index in the templates array (-1 for categories)
}

// SessionTreeItem represents an item in the session tree view (left panel)
type SessionTreeItem struct {
	Type         string       // "session", "window", or "pane"
	Name         string       // Display name
	Session      *TmuxSession // Populated for session items
	Window       *TmuxWindow  // Populated for window items
	Pane         *TmuxPane    // Populated for pane items
	Depth        int          // 0=session, 1=window, 2=pane
	IsLast       bool         // Is this the last item in its level?
	ParentLasts  []bool       // Track which parent levels are last (for tree connectors)
	SessionIndex int          // Index in sessions array
	WindowIndex  int          // Index in windows array (for windows/panes)
	PaneIndex    int          // Index in panes array (for panes)
}

// Session filter constants
const (
	FilterAll      = "all"
	FilterAI       = "ai"
	FilterAttached = "attached"
	FilterDetached = "detached"
)

// TemplateBuilder tracks state for the template creation wizard
type TemplateBuilder struct {
	step        int            // Current step (0-based)
	name        string         // Template name
	description string         // Template description
	category    string         // Category for organization
	workingDir  string         // Working directory
	layout      string         // Layout (e.g., "2x2", "3x3")
	numPanes    int            // Number of panes
	panes       []PaneTemplate // Pane configurations
	currentPane int            // Index of pane being configured
	fieldName   string         // Current field being edited ("name", "description", "category", "working_dir", "layout", "pane_command", "pane_title")
}

// SessionSaveBuilder tracks state for saving a session as a template
type SessionSaveBuilder struct {
	sessionName    string         // Source session name
	name           string         // Template name
	category       string         // Category for organization
	description    string         // Template description
	layout         string         // Detected layout
	panes          []PaneTemplate // Extracted pane configurations
	fieldName      string         // Current field being edited ("name", "description")
	extractedInfo  interface{}    // Raw extracted session info (stored as interface{} to avoid import cycle)
	commonWorkDir  string         // Most common working directory
}

// deleteTemplateConfirmMsg signals that user confirmed template deletion
type deleteTemplateConfirmMsg struct {
	templateIndex int
}

// templateSavedMsg signals that a template was saved
type templateSavedMsg struct {
	template SessionTemplate
	err      error
}

// templateDeletedMsg signals that a template was deleted
type templateDeletedMsg struct {
	templateIndex int
	err           error
}

// sessionExtractedMsg signals that a session has been extracted for saving
type sessionExtractedMsg struct {
	sessionName string
	info        interface{} // ExtractedSessionInfo (stored as interface{} to avoid import cycle)
	err         error
}

// commandEditedMsg signals that the command was edited in external editor
type commandEditedMsg struct {
	content string
	err     error
}
