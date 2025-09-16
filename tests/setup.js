process.env.GITHUB_WORKSPACE = '/tmp/test-workspace';
process.env.GITHUB_REPOSITORY = 'test/repo';
process.env.GITHUB_RUN_ID = '12345';
process.env.AWS_REGION = 'ap-northeast-1';

global.mockGitHubContext = {
  repo: { owner: 'test', repo: 'repo' },
  payload: {
    issue: { number: 123 },
    comment: { body: '/apply' },
  },
};
