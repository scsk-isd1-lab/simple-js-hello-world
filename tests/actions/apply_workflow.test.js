const {
  resolvePullRequestContext,
  findLatestPlanMeta,
} = require('../../scripts/actions/apply_workflow');

describe('resolvePullRequestContext', () => {
  test('sets outputs based on pull request data', async () => {
    const prData = {
      number: 123,
      head: { ref: 'feature-branch', sha: 'abc123' },
      base: { ref: 'main' },
      html_url: 'https://github.com/test/repo/pull/123',
    };

    const github = {
      rest: {
        pulls: {
          get: jest.fn().mockResolvedValue({ data: prData }),
        },
      },
    };

    const context = {
      repo: { owner: 'test', repo: 'repo' },
      payload: { issue: { number: 123 } },
    };

    const core = {
      setOutput: jest.fn(),
    };

    await resolvePullRequestContext({ github, context, core });

    expect(github.rest.pulls.get).toHaveBeenCalledWith({
      owner: 'test',
      repo: 'repo',
      pull_number: 123,
    });

    expect(core.setOutput).toHaveBeenCalledWith('number', '123');
    expect(core.setOutput).toHaveBeenCalledWith('head_ref', 'feature-branch');
    expect(core.setOutput).toHaveBeenCalledWith('head_sha', 'abc123');
    expect(core.setOutput).toHaveBeenCalledWith('base_ref', 'main');
    expect(core.setOutput).toHaveBeenCalledWith(
      'url',
      'https://github.com/test/repo/pull/123',
    );
  });

  test('throws when context is missing issue information', async () => {
    const github = {
      rest: {
        pulls: {
          get: jest.fn(),
        },
      },
    };

    const context = { repo: { owner: 'test', repo: 'repo' }, payload: {} };
    const core = { setOutput: jest.fn() };

    await expect(
      resolvePullRequestContext({ github, context, core }),
    ).rejects.toThrow('insufficient issue payload');
  });
});

describe('findLatestPlanMeta', () => {
  const createGithub = (comments) => ({
    rest: {
      issues: {
        listComments: jest.fn(),
      },
    },
    paginate: jest.fn().mockResolvedValue(comments),
  });

  const context = {
    repo: { owner: 'test', repo: 'repo' },
    payload: { issue: { number: 123 } },
  };

  test('extracts latest session id from plan-meta comments', async () => {
    const comments = [
      {
        user: { login: 'github-actions[bot]' },
        body: '```plan-meta\nsession_id: test-session-123\n```',
      },
    ];

    const core = { setOutput: jest.fn() };
    const sessionId = await findLatestPlanMeta({
      github: createGithub(comments),
      context,
      core,
    });

    expect(sessionId).toBe('test-session-123');
    expect(core.setOutput).toHaveBeenCalledWith('session_id', 'test-session-123');
  });

  test('falls back to pr-based session id when none found', async () => {
    const comments = [
      {
        user: { login: 'other-user' },
        body: 'no plan here',
      },
    ];

    const core = { setOutput: jest.fn() };
    const sessionId = await findLatestPlanMeta({
      github: createGithub(comments),
      context,
      core,
    });

    expect(sessionId).toBe('pr-123');
    expect(core.setOutput).toHaveBeenCalledWith('session_id', 'pr-123');
  });
});
