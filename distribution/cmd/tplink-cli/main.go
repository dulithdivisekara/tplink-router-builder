package main

import (
	"fmt"
	"os"
	"os/exec"
)

// Universal Go Wrapper for TP-Link Router Suite CLI
// Author: Dulith Divisekara (SLIIT Malabe)
func main() {
	pyBin := "python3"
	if _, err := exec.LookPath(pyBin); err != nil {
		pyBin = "python"
	}

	args := append([]string{"-m", "tplink_router.cli.main"}, os.Args[1:]...)
	cmd := exec.Command(pyBin, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin

	if err := cmd.Run(); err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			os.Exit(exitErr.ExitCode())
		}
		fmt.Fprintf(os.Stderr, "Error executing tplink-cli: %v\n", err)
		os.Exit(1)
	}
}
