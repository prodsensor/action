#!/usr/bin/env python3
"""
ProdSensor GitHub Action
Runs production readiness analysis and posts results to PRs
"""

import os
import sys
import json
import time
from typing import Optional, Dict, Any

import httpx


# Exit codes
EXIT_PRODUCTION_READY = 0
EXIT_NOT_PRODUCTION_READY = 1
EXIT_CONDITIONALLY_READY = 2
EXIT_API_ERROR = 3
EXIT_AUTH_ERROR = 4
EXIT_TIMEOUT = 5


class ProdSensorAction:
    """GitHub Action for ProdSensor analysis"""

    DEFAULT_API_URL = "https://ps-production-5531.up.railway.app"

    def __init__(self):
        # Read inputs from environment
        self.api_key = os.environ.get("PRODSENSOR_API_KEY")
        # Use 'or' to handle empty string (when input not provided)
        self.api_url = (os.environ.get("PRODSENSOR_API_URL") or self.DEFAULT_API_URL).rstrip("/")
        self.repo_url = os.environ.get("INPUT_REPO_URL")
        self.fail_on = os.environ.get("INPUT_FAIL_ON", "not-ready")
        self.comment_on_pr = os.environ.get("INPUT_COMMENT_ON_PR", "true").lower() == "true"
        self.timeout = int(os.environ.get("INPUT_TIMEOUT", "600"))

        # GitHub context
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.github_repository = os.environ.get("GITHUB_REPOSITORY")
        self.github_event_name = os.environ.get("GITHUB_EVENT_NAME")
        self.github_event_path = os.environ.get("GITHUB_EVENT_PATH")

        # Determine repo URL if not provided
        if not self.repo_url and self.github_repository:
            self.repo_url = f"https://github.com/{self.github_repository}"

    def log(self, message: str, level: str = "info"):
        """Log a message using GitHub Actions format"""
        if level == "error":
            print(f"::error::{message}")
        elif level == "warning":
            print(f"::warning::{message}")
        elif level == "debug":
            print(f"::debug::{message}")
        else:
            print(message)

    def set_output(self, name: str, value: Any):
        """Set a GitHub Actions output"""
        output_file = os.environ.get("GITHUB_OUTPUT")
        if output_file:
            with open(output_file, "a") as f:
                f.write(f"{name}={value}\n")
        else:
            print(f"::set-output name={name}::{value}")

    def get_pr_number(self) -> Optional[int]:
        """Get PR number from event context"""
        if not self.github_event_path:
            return None

        try:
            with open(self.github_event_path) as f:
                event = json.load(f)

            if self.github_event_name == "pull_request":
                return event.get("pull_request", {}).get("number")
            elif self.github_event_name == "pull_request_target":
                return event.get("pull_request", {}).get("number")

            return None
        except Exception as e:
            self.log(f"Failed to read event file: {e}", "debug")
            return None

    def api_request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make an API request"""
        headers = {
            "X-API-Key": self.api_key,
            "User-Agent": "prodsensor-github-action/1.0.0"
        }

        with httpx.Client(base_url=self.api_url, headers=headers, timeout=30.0) as client:
            response = client.request(method, path, **kwargs)

            if response.status_code == 401:
                raise Exception("Invalid API key")
            elif response.status_code == 429:
                raise Exception("Rate limit exceeded")
            elif response.status_code >= 400:
                error = response.json().get("detail", response.text)
                raise Exception(f"API error: {error}")

            return response.json()

    def start_analysis(self) -> str:
        """Start analysis and return run ID"""
        self.log(f"Starting analysis of {self.repo_url}")

        result = self.api_request("POST", "/v1/analyze/repo", json={
            "repo_url": self.repo_url
        })

        # API returns 'id', not 'run_id'
        return result.get("run_id") or result.get("id")

    def get_status(self, run_id: str) -> Dict[str, Any]:
        """Get analysis status"""
        return self.api_request("GET", f"/v1/runs/{run_id}")

    def get_report(self, run_id: str) -> Dict[str, Any]:
        """Get full analysis report"""
        return self.api_request("GET", f"/v1/runs/{run_id}/report.json")

    def wait_for_completion(self, run_id: str) -> Dict[str, Any]:
        """Wait for analysis to complete"""
        start_time = time.time()
        poll_interval = 5

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                raise TimeoutError(f"Analysis timed out after {self.timeout}s")

            status = self.get_status(run_id)

            if status["status"] == "COMPLETE":
                return status
            elif status["status"] == "FAILED":
                raise Exception(f"Analysis failed: {status.get('error', 'Unknown error')}")

            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            self.log(f"Status: {status['status']} ({minutes}m {seconds}s elapsed)")

            time.sleep(poll_interval)

    def format_pr_comment(self, report: Dict[str, Any], run_id: str) -> str:
        """Format analysis results as a PR comment"""
        verdict = report.get("verdict", "UNKNOWN")
        score = report.get("score", "N/A")

        # Verdict emoji and color
        if verdict == "PRODUCTION_READY":
            verdict_emoji = ":white_check_mark:"
            verdict_text = "**PRODUCTION READY**"
        elif verdict == "NOT_PRODUCTION_READY":
            verdict_emoji = ":x:"
            verdict_text = "**NOT PRODUCTION READY**"
        else:
            verdict_emoji = ":warning:"
            verdict_text = "**CONDITIONALLY READY**"

        # Count findings
        findings = report.get("findings", [])
        blockers = len([f for f in findings if f.get("severity") == "Blocker"])
        majors = len([f for f in findings if f.get("severity") == "Major"])
        minors = len([f for f in findings if f.get("severity") == "Minor"])

        comment = f"""## {verdict_emoji} ProdSensor Analysis

{verdict_text}

**Score:** {score}/100

### Findings Summary
| Severity | Count |
|----------|-------|
| :rotating_light: Blockers | {blockers} |
| :warning: Major | {majors} |
| :information_source: Minor | {minors} |

"""

        # Add dimension scores
        dimensions = report.get("dimensions", {})
        if dimensions:
            comment += "### Dimension Scores\n"
            comment += "| Dimension | Score | Status |\n"
            comment += "|-----------|-------|--------|\n"

            for name, data in dimensions.items():
                dim_score = data.get("score", 0)
                if dim_score >= 70:
                    status = ":green_circle:"
                elif dim_score >= 50:
                    status = ":yellow_circle:"
                else:
                    status = ":red_circle:"

                comment += f"| {name.replace('_', ' ').title()} | {dim_score} | {status} |\n"

        # Add top blockers
        blocker_findings = [f for f in findings if f.get("severity") == "Blocker"]
        if blocker_findings:
            comment += "\n### :rotating_light: Blockers (Must Fix)\n\n"
            for finding in blocker_findings[:5]:
                title = finding.get("title", "Untitled")
                desc = finding.get("description", "")[:200]
                comment += f"- **{title}**\n  {desc}\n\n"

            if len(blocker_findings) > 5:
                comment += f"*...and {len(blocker_findings) - 5} more blockers*\n"

        comment += f"\n---\n*Analyzed by [ProdSensor](https://prodsensor.com) | [View Full Report]({self.api_url}/v1/runs/{run_id}/report.json)*"

        return comment

    def post_pr_comment(self, comment: str):
        """Post a comment on the PR"""
        pr_number = self.get_pr_number()
        if not pr_number:
            self.log("Not a PR context, skipping comment", "debug")
            return

        if not self.github_token:
            self.log("GITHUB_TOKEN not available, skipping comment", "warning")
            return

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"https://api.github.com/repos/{self.github_repository}/issues/{pr_number}/comments",
                    headers={
                        "Authorization": f"Bearer {self.github_token}",
                        "Accept": "application/vnd.github.v3+json"
                    },
                    json={"body": comment}
                )

                if response.status_code != 201:
                    self.log(f"Failed to post comment: {response.text}", "warning")
                else:
                    self.log("Posted analysis results to PR")

        except Exception as e:
            self.log(f"Failed to post PR comment: {e}", "warning")

    def run(self) -> int:
        """Run the action and return exit code"""
        # Validate inputs
        if not self.api_key:
            self.log("API key is required", "error")
            return EXIT_AUTH_ERROR

        if not self.repo_url:
            self.log("Could not determine repository URL", "error")
            return EXIT_API_ERROR

        try:
            # Start analysis
            self.log("::group::Starting Analysis")
            run_id = self.start_analysis()
            self.set_output("run-id", run_id)
            self.log(f"Analysis started. Run ID: {run_id}")
            self.log("::endgroup::")

            # Wait for completion
            self.log("::group::Waiting for Analysis")
            status = self.wait_for_completion(run_id)
            self.log("::endgroup::")

            # Get full report
            self.log("::group::Getting Report")
            report = self.get_report(run_id)
            self.log("::endgroup::")

            # Extract results
            verdict = report.get("verdict", "UNKNOWN")
            score = report.get("score")
            findings = report.get("findings", [])
            blocker_count = len([f for f in findings if f.get("severity") == "Blocker"])
            major_count = len([f for f in findings if f.get("severity") == "Major"])

            # Set outputs
            self.set_output("verdict", verdict)
            self.set_output("score", score or "")
            self.set_output("report-url", f"{self.api_url}/v1/runs/{run_id}/report.json")
            self.set_output("blocker-count", blocker_count)
            self.set_output("major-count", major_count)

            # Print summary
            self.log("")
            self.log("=" * 50)
            self.log(f"VERDICT: {verdict}")
            self.log(f"SCORE: {score}/100")
            self.log(f"BLOCKERS: {blocker_count}")
            self.log(f"MAJOR: {major_count}")
            self.log("=" * 50)

            # Post PR comment
            if self.comment_on_pr:
                comment = self.format_pr_comment(report, run_id)
                self.post_pr_comment(comment)

            # Determine exit code
            if self.fail_on == "never":
                return EXIT_PRODUCTION_READY
            elif self.fail_on == "blockers":
                if blocker_count > 0:
                    self.log(f"Failing build: {blocker_count} blocker(s) found", "error")
                    return EXIT_NOT_PRODUCTION_READY
                return EXIT_PRODUCTION_READY
            else:  # not-ready (default)
                if verdict == "PRODUCTION_READY":
                    return EXIT_PRODUCTION_READY
                elif verdict == "CONDITIONALLY_READY":
                    self.log("Build warning: conditionally ready", "warning")
                    return EXIT_CONDITIONALLY_READY
                else:
                    self.log(f"Failing build: {verdict}", "error")
                    return EXIT_NOT_PRODUCTION_READY

        except TimeoutError as e:
            self.log(str(e), "error")
            return EXIT_TIMEOUT
        except Exception as e:
            self.log(f"Error: {e}", "error")
            if "Invalid API key" in str(e):
                return EXIT_AUTH_ERROR
            return EXIT_API_ERROR


if __name__ == "__main__":
    action = ProdSensorAction()
    exit_code = action.run()
    sys.exit(exit_code)
