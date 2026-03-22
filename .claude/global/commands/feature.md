---
description: "Plan and scaffold a new feature. Runs an analyst conversation, then creates a GitHub issue and branch."
allowed-tools: Bash, Read, Glob, Grep
---

You are orchestrating a feature planning workflow. Follow these steps in order.

## Step 1: Analysis

Invoke the analyst-agent with the following feature idea: $ARGUMENTS

## Step 2: Handoff

Once the user has confirmed the feature description with the analyst-agent, invoke the gh-agent with the approved description.

## Step 3: Done

The gh-agent will report the issue URL and branch. Relay this to the user.
