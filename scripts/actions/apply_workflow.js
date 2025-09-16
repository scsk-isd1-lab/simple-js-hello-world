"use strict";

const DEFAULT_BOT_NAMES = new Set(["github-actions[bot]", "github-actions"]);

async function resolvePullRequestContext({ github, context, core }) {
  if (!github || !context || !core) {
    throw new Error("resolvePullRequestContext: missing github/context/core");
  }

  const owner = context.repo?.owner;
  const repo = context.repo?.repo;
  const pullNumber = context.payload?.issue?.number;

  if (!owner || !repo || !pullNumber) {
    throw new Error("resolvePullRequestContext: insufficient issue payload");
  }

  const { data: pr } = await github.rest.pulls.get({
    owner,
    repo,
    pull_number: pullNumber,
  });

  core.setOutput("number", pr.number?.toString() ?? "");
  core.setOutput("head_ref", pr.head?.ref ?? "");
  core.setOutput("head_sha", pr.head?.sha ?? "");
  core.setOutput("base_ref", pr.base?.ref ?? "");
  core.setOutput("url", pr.html_url ?? "");

  return pr;
}

async function findLatestPlanMeta({
  github,
  context,
  core,
  issueNumber,
  botNames = DEFAULT_BOT_NAMES,
}) {
  if (!github || !context || !core) {
    throw new Error("findLatestPlanMeta: missing github/context/core");
  }

  const owner = context.repo?.owner;
  const repo = context.repo?.repo;
  const number = issueNumber ?? context.payload?.issue?.number;

  if (!owner || !repo || !number) {
    throw new Error("findLatestPlanMeta: insufficient issue context");
  }

  const comments = await github.paginate(github.rest.issues.listComments, {
    owner,
    repo,
    issue_number: number,
    per_page: 100,
  });

  for (let i = comments.length - 1; i >= 0; i -= 1) {
    const comment = comments[i];
    const body = `${comment?.body ?? ""}`;
    const author = comment?.user?.login ?? "";

    if (!botNames.has(author) || !body.includes("```plan-meta")) {
      continue;
    }

    const block = body.match(/```plan-meta[\s\S]*?```/);
    if (!block) {
      continue;
    }

    const sessionId = block[0]
      .match(/session_id\s*:\s*(.+)/)?.[1]
      ?.trim();

    if (sessionId) {
      core.setOutput("session_id", sessionId);
      return sessionId;
    }
  }

  const fallback = `pr-${number}`;
  core.setOutput("session_id", fallback);
  return fallback;
}

module.exports = {
  resolvePullRequestContext,
  findLatestPlanMeta,
  DEFAULT_BOT_NAMES,
};
