package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
	"syscall"
	"time"
)

// tmux.go - Tmux Integration Layer
// Purpose: Interface with tmux for session/window/pane management
// When to extend: Add new tmux commands or operations here

// checkTmuxRunning checks if tmux server is running
func checkTmuxRunning() bool {
	cmd := exec.Command("tmux", "info")
	err := cmd.Run()
	return err == nil
}

// getGitBranch returns the current git branch for a directory, or empty string if not in a git repo
func getGitBranch(dir string) string {
	cmd := exec.Command("git", "-C", dir, "rev-parse", "--abbrev-ref", "HEAD")
	output, err := cmd.Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(output))
}

// startTmuxServer starts the tmux server if not running
func startTmuxServer() error {
	if checkTmuxRunning() {
		return nil
	}
	cmd := exec.Command("tmux", "start-server")
	return cmd.Run()
}

// listSessions returns all tmux sessions
func listSessions() ([]TmuxSession, error) {
	// Ensure tmux server is running
	if err := startTmuxServer(); err != nil {
		return nil, fmt.Errorf("failed to start tmux server: %w", err)
	}

	// Format: session_name|session_windows|session_attached|session_created
	cmd := exec.Command("tmux", "list-sessions", "-F", "#{session_name}|#{session_windows}|#{session_attached}|#{session_created}")
	output, err := cmd.Output()
	if err != nil {
		// No sessions exist yet - return empty list
		if strings.Contains(err.Error(), "no server running") || strings.Contains(err.Error(), "no sessions") {
			return []TmuxSession{}, nil
		}
		return nil, fmt.Errorf("failed to list sessions: %w", err)
	}

	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	sessions := make([]TmuxSession, 0, len(lines))

	for _, line := range lines {
		if line == "" {
			continue
		}

		parts := strings.Split(line, "|")
		if len(parts) < 4 {
			continue
		}

		// Parse attached count - session is attached if count >= 1
		attachedCount := 0
		fmt.Sscanf(parts[2], "%d", &attachedCount)

		session := TmuxSession{
			Name:       parts[0],
			Attached:   attachedCount >= 1,
			Created:    formatTime(parts[3]),
			LastActive: "active", // Will be updated
		}

		// Parse window count
		fmt.Sscanf(parts[1], "%d", &session.Windows)

		// Get working directory for the first pane
		workingDirCmd := exec.Command("tmux", "display-message", "-p", "-t", session.Name+":0.0", "#{pane_current_path}")
		workingDirOutput, err := workingDirCmd.Output()
		if err == nil {
			session.WorkingDir = strings.TrimSpace(string(workingDirOutput))
			// Get git branch if in a git repo
			session.GitBranch = getGitBranch(session.WorkingDir)
		}

		// Detect AI tool type and set appropriate fields
		if detectClaudeSession(session.Name) {
			session.AITool = "claude"
			// Get the pane ID for the first pane
			paneCmd := exec.Command("tmux", "display-message", "-p", "-t", session.Name+":0.0", "#{pane_id}")
			paneOutput, err := paneCmd.Output()
			paneID := ""
			if err == nil {
				paneID = strings.TrimSpace(string(paneOutput))
			}

			state, err := getClaudeStateForSession(session.Name, paneID)
			if err == nil {
				session.ClaudeState = state
			} else {
				// No state file found - Claude hasn't started or no hooks fired yet
				// Create a default "ready" state
				session.ClaudeState = &ClaudeState{
					SessionID:   session.Name,
					Status:      "idle",
					CurrentTool: "",
					WorkingDir:  session.WorkingDir,
					LastUpdated: time.Now().UTC().Format(time.RFC3339),
					TmuxPane:    paneID,
					PID:         0,
					HookType:    "default",
					Details:     map[string]interface{}{"event": "no_state_file", "message": "Ready (no activity yet)"},
				}
			}
		} else if detectCodexSession(session.Name) {
			session.AITool = "codex"
		} else if detectGeminiSession(session.Name) {
			session.AITool = "gemini"
		}

		sessions = append(sessions, session)
	}

	return sessions, nil
}

// listWindows returns windows for a session
func listWindows(sessionName string) ([]TmuxWindow, error) {
	// Format: window_index|window_name|window_panes|window_active
	cmd := exec.Command("tmux", "list-windows", "-t", sessionName, "-F", "#{window_index}|#{window_name}|#{window_panes}|#{window_active}")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to list windows for session %s: %w", sessionName, err)
	}

	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	windows := make([]TmuxWindow, 0, len(lines))

	for _, line := range lines {
		if line == "" {
			continue
		}

		parts := strings.Split(line, "|")
		if len(parts) < 4 {
			continue
		}

		window := TmuxWindow{
			Name:   parts[1],
			Active: parts[3] == "1",
		}

		fmt.Sscanf(parts[0], "%d", &window.Index)
		fmt.Sscanf(parts[2], "%d", &window.Panes)

		windows = append(windows, window)
	}

	return windows, nil
}

// listPanes returns panes for a window
func listPanes(sessionName string, windowIndex int) ([]TmuxPane, error) {
	target := fmt.Sprintf("%s:%d", sessionName, windowIndex)
	// Format: pane_id|pane_index|pane_width|pane_height|pane_active|pane_current_command
	cmd := exec.Command("tmux", "list-panes", "-t", target, "-F", "#{pane_id}|#{pane_index}|#{pane_width}|#{pane_height}|#{pane_active}|#{pane_current_command}")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to list panes for %s: %w", target, err)
	}

	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	panes := make([]TmuxPane, 0, len(lines))

	for _, line := range lines {
		if line == "" {
			continue
		}

		parts := strings.Split(line, "|")
		if len(parts) < 6 {
			continue
		}

		pane := TmuxPane{
			ID:      parts[0],
			Active:  parts[4] == "1",
			Command: parts[5],
		}

		fmt.Sscanf(parts[1], "%d", &pane.Index)
		fmt.Sscanf(parts[2], "%d", &pane.Width)
		fmt.Sscanf(parts[3], "%d", &pane.Height)

		panes = append(panes, pane)
	}

	return panes, nil
}

// capturePane returns full scrollback content of a pane
// Uses -S - to capture from beginning of history (not just visible area)
func capturePane(paneID string) (string, error) {
	cmd := exec.Command("tmux", "capture-pane", "-p", "-S", "-", "-t", paneID)
	output, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("failed to capture pane %s: %w", paneID, err)
	}
	return string(output), nil
}

// attachSession attaches to a session (switches client)
func attachSession(sessionName string) error {
	cmd := exec.Command("tmux", "attach-session", "-t", sessionName)
	return cmd.Run()
}

// switchClient switches the current client to a session (for popup mode)
func switchClient(sessionName string) error {
	cmd := exec.Command("tmux", "switch-client", "-t", sessionName)
	return cmd.Run()
}

// attachToSession attaches to a session, handling both inside and outside tmux
func attachToSession(sessionName string) error {
	// Check if we're running inside tmux
	// When inside tmux, $TMUX environment variable is set
	// We need to use switch-client instead of attach-session
	insideTmux := isInsideTmux()

	if insideTmux {
		// Use switch-client when inside tmux
		return switchClient(sessionName)
	} else {
		// Use attach-session when outside tmux
		// We need to replace the current process with tmux using syscall.Exec
		// This is the only way to properly hand off control to tmux
		tmuxPath, err := exec.LookPath("tmux")
		if err != nil {
			return fmt.Errorf("tmux not found in PATH: %w", err)
		}

		// Replace current process with: tmux attach-session -t sessionName
		args := []string{"tmux", "attach-session", "-t", sessionName}
		env := os.Environ()

		// syscall.Exec replaces the current process with tmux
		// If this succeeds, this function never returns
		err = syscall.Exec(tmuxPath, args, env)
		if err != nil {
			return fmt.Errorf("failed to exec tmux: %w", err)
		}

		// We should never reach here if Exec succeeds
		return nil
	}
}

// createSession creates a new tmux session
func createSession(sessionName string) error {
	cmd := exec.Command("tmux", "new-session", "-d", "-s", sessionName)
	return cmd.Run()
}

// killSession kills a tmux session
func killSession(sessionName string) error {
	cmd := exec.Command("tmux", "kill-session", "-t", sessionName)
	return cmd.Run()
}

// detachSession detaches from a tmux session
func detachSession(sessionName string) error {
	cmd := exec.Command("tmux", "detach-client", "-s", sessionName)
	return cmd.Run()
}

// renameSession renames a session
func renameSession(oldName, newName string) error {
	cmd := exec.Command("tmux", "rename-session", "-t", oldName, newName)
	return cmd.Run()
}

// sendKeys sends keys to a target session/window/pane
func sendKeys(target, keys string) error {
	cmd := exec.Command("tmux", "send-keys", "-t", target, keys, "Enter")
	return cmd.Run()
}

// Helper functions

// formatTime formats a unix timestamp to a readable string
func formatTime(unixStr string) string {
	var timestamp int64
	fmt.Sscanf(unixStr, "%d", &timestamp)

	if timestamp == 0 {
		return "unknown"
	}

	t := time.Unix(timestamp, 0)
	now := time.Now()

	diff := now.Sub(t)

	if diff < time.Minute {
		return "just now"
	} else if diff < time.Hour {
		mins := int(diff.Minutes())
		return fmt.Sprintf("%dm ago", mins)
	} else if diff < 24*time.Hour {
		hours := int(diff.Hours())
		return fmt.Sprintf("%dh ago", hours)
	} else {
		days := int(diff.Hours() / 24)
		if days == 1 {
			return "1 day ago"
		}
		return fmt.Sprintf("%d days ago", days)
	}
}

// formatSessionSummary creates a summary line for a session
func formatSessionSummary(session TmuxSession) string {
	attachedIcon := " "
	if session.Attached {
		attachedIcon = "●"
	}

	return fmt.Sprintf("%s %s (%d windows) - %s", attachedIcon, session.Name, session.Windows, session.Created)
}

// Template-based session creation functions

// createSessionFromTemplate creates a new tmux session from a template
// Returns the name of the created session and any error
func createSessionFromTemplate(template SessionTemplate) (string, error) {
	return createSessionFromTemplateInternal(template, "")
}

// createSessionFromTemplateWithOverride creates a new tmux session from a template with optional working directory override
// Returns the name of the created session and any error
func createSessionFromTemplateWithOverride(template SessionTemplate, cwdOverride string) (string, error) {
	return createSessionFromTemplateInternal(template, cwdOverride)
}

// createSessionFromTemplateInternal is the internal implementation that accepts an optional cwd override
// Returns the name of the created session and any error
func createSessionFromTemplateInternal(template SessionTemplate, cwdOverride string) (string, error) {
	// Generate unique session name
	sessionName := generateUniqueSessionName(template.Name)

	// Expand working directory
	workingDir := expandPath(template.WorkingDir)

	// CLI override takes precedence
	if cwdOverride != "" {
		workingDir = expandPath(cwdOverride)
	}

	// Parse layout (e.g., "2x2" = 2 columns, 2 rows)
	cols, rows, err := parseLayout(template.Layout)
	if err != nil {
		return "", fmt.Errorf("invalid layout %s: %w", template.Layout, err)
	}

	// Validate we have enough panes in template
	expectedPanes := cols * rows
	if len(template.Panes) < expectedPanes {
		return "", fmt.Errorf("template has %d panes but layout %s requires %d panes",
			len(template.Panes), template.Layout, expectedPanes)
	}

	// Create the base session with first pane
	cmd := exec.Command("tmux", "new-session", "-d", "-s", sessionName, "-c", workingDir)
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("failed to create session: %w", err)
	}

	// Create the grid layout
	if err := createGridLayout(sessionName, cols, rows, workingDir); err != nil {
		// Clean up session on failure
		exec.Command("tmux", "kill-session", "-t", sessionName).Run()
		return "", fmt.Errorf("failed to create layout: %w", err)
	}

	// Send commands to each pane
	paneIndex := 0
	for row := 0; row < rows; row++ {
		for col := 0; col < cols; col++ {
			if paneIndex < len(template.Panes) {
				paneTemplate := template.Panes[paneIndex]
				target := fmt.Sprintf("%s.%d", sessionName, paneIndex)

				// Change to pane-specific working directory if specified
				if paneTemplate.WorkingDir != "" {
					paneWorkingDir := expandPath(paneTemplate.WorkingDir)
					cdCmd := fmt.Sprintf("cd %s", paneWorkingDir)
					if err := sendKeysNoEnter(target, cdCmd); err != nil {
						return "", fmt.Errorf("failed to change directory in pane %d: %w", paneIndex, err)
					}
				}

				// Send the main command
				if paneTemplate.Command != "" {
					if err := sendKeysNoEnter(target, paneTemplate.Command); err != nil {
						return "", fmt.Errorf("failed to send command to pane %d: %w", paneIndex, err)
					}
				}

				paneIndex++
			}
		}
	}

	return sessionName, nil
}

// createGridLayout creates a grid of panes (cols x rows)
func createGridLayout(sessionName string, cols, rows int, workingDir string) error {
	totalPanes := cols * rows

	// Strategy: Create all panes first, then arrange them with tiled layout
	// This is much more reliable than trying to manually track pane indices
	// which shift as tmux creates new panes

	// Create (totalPanes - 1) additional panes (we start with 1)
	for i := 1; i < totalPanes; i++ {
		cmd := exec.Command("tmux", "split-window", "-t", sessionName+":0", "-c", workingDir)
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to create pane %d: %w", i, err)
		}
		time.Sleep(10 * time.Millisecond)
	}

	// Use tmux's tiled layout to arrange panes evenly in a grid
	cmd := exec.Command("tmux", "select-layout", "-t", sessionName+":0", "tiled")
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to apply tiled layout: %w", err)
	}

	return nil
}

// sendKeysNoEnter sends keys to a tmux pane without pressing Enter
func sendKeysNoEnter(target, keys string) error {
	cmd := exec.Command("tmux", "send-keys", "-t", target, keys, "C-m")
	return cmd.Run()
}

// parseLayout parses a layout string like "2x2" into (cols, rows)
func parseLayout(layout string) (int, int, error) {
	parts := strings.Split(layout, "x")
	if len(parts) != 2 {
		return 0, 0, fmt.Errorf("layout must be in format 'COLSxROWS' (e.g., '2x2')")
	}

	var cols, rows int
	fmt.Sscanf(parts[0], "%d", &cols)
	fmt.Sscanf(parts[1], "%d", &rows)

	if cols < 1 || rows < 1 {
		return 0, 0, fmt.Errorf("invalid dimensions: %dx%d", cols, rows)
	}

	return cols, rows, nil
}

// generateUniqueSessionName generates a unique session name based on template name
func generateUniqueSessionName(baseName string) string {
	// Clean the base name (remove special characters, spaces -> hyphens)
	cleaned := strings.ToLower(baseName)
	cleaned = strings.ReplaceAll(cleaned, " ", "-")
	cleaned = strings.Map(func(r rune) rune {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '-' {
			return r
		}
		return -1
	}, cleaned)

	// Check if session exists
	sessions, _ := listSessions()
	nameExists := false
	for _, session := range sessions {
		if session.Name == cleaned {
			nameExists = true
			break
		}
	}

	if !nameExists {
		return cleaned
	}

	// Add timestamp suffix to make it unique
	timestamp := time.Now().Format("150405") // HHMMSS
	return fmt.Sprintf("%s-%s", cleaned, timestamp)
}

// expandPath expands ~ to home directory
func expandPath(path string) string {
	if strings.HasPrefix(path, "~") {
		// Get home directory using tmux's environment
		if homeDir, err := exec.Command("sh", "-c", "echo $HOME").Output(); err == nil {
			home := strings.TrimSpace(string(homeDir))
			return strings.Replace(path, "~", home, 1)
		}
	}
	return path
}

// isInsideTmux checks if the program is running inside a tmux session
func isInsideTmux() bool {
	// When running inside tmux, the $TMUX environment variable is set
	// It contains the socket path and session ID
	return exec.Command("sh", "-c", "[ -n \"$TMUX\" ]").Run() == nil
}

// getCurrentSessionName returns the name of the current tmux session (or empty string if not in tmux)
func getCurrentSessionName() string {
	if !isInsideTmux() {
		return ""
	}

	cmd := exec.Command("tmux", "display-message", "-p", "#S")
	output, err := cmd.Output()
	if err != nil {
		return ""
	}

	return strings.TrimSpace(string(output))
}

// detachClient detaches from the current tmux session
func detachClient() error {
	cmd := exec.Command("tmux", "detach-client")
	return cmd.Run()
}

// detachAndLaunchFullscreen detaches from tmux and launches conductor-tui in the original terminal
// Uses tmux's -E flag to run a command after detaching
func detachAndLaunchFullscreen() error {
	// Get the path to the current conductor-tui executable
	execPath, err := os.Executable()
	if err != nil {
		// Fallback to "conductor-tui" if we can't determine the path
		execPath = "conductor-tui"
	}

	// Detach and run conductor-tui in normal mode (not popup)
	cmd := exec.Command("tmux", "detach-client", "-E", execPath)
	return cmd.Run()
}

// extractSessionInfo extracts complete session info for saving as a template
// Returns pane info with working directories, commands, and dimensions
type ExtractedPaneInfo struct {
	WorkingDir string
	Command    string
	Title      string
	Width      int
	Height     int
	Left       int
	Top        int
}

type ExtractedSessionInfo struct {
	Panes       []ExtractedPaneInfo
	WindowIndex int
	WindowName  string
}

// extractSessionInfo extracts info from a session's active window
func extractSessionInfo(sessionName string) (*ExtractedSessionInfo, error) {
	// Get the active window for this session
	windows, err := listWindows(sessionName)
	if err != nil {
		return nil, fmt.Errorf("failed to get windows: %w", err)
	}

	if len(windows) == 0 {
		return nil, fmt.Errorf("no windows found in session")
	}

	// Find the active window
	activeWindowIndex := 0
	activeWindowName := windows[0].Name
	for _, window := range windows {
		if window.Active {
			activeWindowIndex = window.Index
			activeWindowName = window.Name
			break
		}
	}

	// Get detailed pane info with working directories
	target := fmt.Sprintf("%s:%d", sessionName, activeWindowIndex)

	// Format: pane_id|pane_index|pane_width|pane_height|pane_left|pane_top|pane_current_path|pane_current_command|pane_title
	cmd := exec.Command("tmux", "list-panes", "-t", target, "-F",
		"#{pane_index}|#{pane_width}|#{pane_height}|#{pane_left}|#{pane_top}|#{pane_current_path}|#{pane_current_command}|#{pane_title}")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to get pane info: %w", err)
	}

	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	panes := make([]ExtractedPaneInfo, 0, len(lines))

	for _, line := range lines {
		if line == "" {
			continue
		}

		parts := strings.Split(line, "|")
		if len(parts) < 8 {
			continue
		}

		pane := ExtractedPaneInfo{
			WorkingDir: parts[5],
			Command:    parts[6],
			Title:      parts[7],
		}

		fmt.Sscanf(parts[1], "%d", &pane.Width)
		fmt.Sscanf(parts[2], "%d", &pane.Height)
		fmt.Sscanf(parts[3], "%d", &pane.Left)
		fmt.Sscanf(parts[4], "%d", &pane.Top)

		panes = append(panes, pane)
	}

	return &ExtractedSessionInfo{
		Panes:       panes,
		WindowIndex: activeWindowIndex,
		WindowName:  activeWindowName,
	}, nil
}

// detectGridLayout attempts to detect the grid layout (e.g., "2x2") from pane positions
// Returns the layout string or "custom" if it's not a simple grid
func detectGridLayout(panes []ExtractedPaneInfo) string {
	if len(panes) == 0 {
		return "1x1"
	}

	// For simple grids, panes should align on rows and columns
	// Count unique Left positions (columns) and Top positions (rows)
	leftPositions := make(map[int]bool)
	topPositions := make(map[int]bool)

	for _, pane := range panes {
		leftPositions[pane.Left] = true
		topPositions[pane.Top] = true
	}

	cols := len(leftPositions)
	rows := len(topPositions)

	// Validate it's a complete grid
	if cols*rows != len(panes) {
		return "custom"
	}

	return fmt.Sprintf("%dx%d", cols, rows)
}

// sendKeysToSession sends a command to a tmux session
func sendKeysToSession(sessionName, command string) error {
	// Send the command text first
	cmd := exec.Command("tmux", "send-keys", "-t", sessionName, command)
	if err := cmd.Run(); err != nil {
		return err
	}

	// Small delay to ensure the command is fully typed before pressing Enter
	// This prevents the terminal from adding a newline instead of submitting
	time.Sleep(100 * time.Millisecond)

	// Send Enter key separately
	enterCmd := exec.Command("tmux", "send-keys", "-t", sessionName, "Enter")
	return enterCmd.Run()
}

// sendKeysToPane sends a command to a specific tmux pane
func sendKeysToPane(paneID, command string) error {
	// Send the command text first
	cmd := exec.Command("tmux", "send-keys", "-t", paneID, command)
	if err := cmd.Run(); err != nil {
		return err
	}

	// Small delay to ensure the command is fully typed before pressing Enter
	time.Sleep(100 * time.Millisecond)

	// Send Enter key separately
	enterCmd := exec.Command("tmux", "send-keys", "-t", paneID, "Enter")
	return enterCmd.Run()
}
