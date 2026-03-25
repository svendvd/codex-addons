#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const DEFAULT_DAILY_BUDGET_PERCENT = 13;
const DEFAULT_DAILY_CUTOFF_HOUR = 17;
const DEFAULT_SOURCE = 'exec';
const HELP_TEXT = `Usage: codex-usage-status [options]

Inspect the latest Codex rollout rate limits for a given source.

Options:
  --json                Print machine-readable JSON
  --show-paths          Include redacted Codex paths in JSON output
  --source=<name>       Rollout source to inspect (default: ${DEFAULT_SOURCE})
  --daily-budget-percent=<n>
                        Budget percent subtracted per remaining day (default: ${DEFAULT_DAILY_BUDGET_PERCENT})
  --daily-cutoff-hour=<0-23>
                        Local hour used to count remaining days (default: ${DEFAULT_DAILY_CUTOFF_HOUR})
  --codex-home=<path>   Override CODEX_HOME (default: $CODEX_HOME or ~/.codex)
  --help                Show this help message
`;

function expandHomePath(value) {
  if (!value) {
    return value;
  }

  if (value === '~') {
    return os.homedir();
  }

  if (value.startsWith('~/')) {
    return path.join(os.homedir(), value.slice(2));
  }

  return value;
}

function abbreviateHome(filePath) {
  const homeDir = os.homedir();
  const resolvedPath = path.resolve(filePath);

  if (resolvedPath === homeDir) {
    return '~';
  }

  if (resolvedPath.startsWith(`${homeDir}${path.sep}`)) {
    return `~${resolvedPath.slice(homeDir.length)}`;
  }

  return resolvedPath;
}

function escapeSqlLiteral(value) {
  return value.replace(/'/g, "''");
}

function parseArgs(argv) {
  const options = {
    codexHome: null,
    dailyBudgetPercent: DEFAULT_DAILY_BUDGET_PERCENT,
    dailyCutoffHour: DEFAULT_DAILY_CUTOFF_HOUR,
    json: false,
    showPaths: false,
    source: DEFAULT_SOURCE,
  };

  for (const arg of argv) {
    if (arg === '--json') {
      options.json = true;
      continue;
    }

    if (arg === '--show-paths') {
      options.showPaths = true;
      continue;
    }

    if (arg === '--help' || arg === '-h') {
      process.stdout.write(HELP_TEXT);
      process.exit(0);
    }

    if (arg.startsWith('--source=')) {
      options.source = arg.slice('--source='.length);
      continue;
    }

    if (arg.startsWith('--daily-budget-percent=')) {
      options.dailyBudgetPercent = parseDailyBudgetPercent(arg.slice('--daily-budget-percent='.length));
      continue;
    }

    if (arg.startsWith('--daily-cutoff-hour=')) {
      options.dailyCutoffHour = parseDailyCutoffHour(arg.slice('--daily-cutoff-hour='.length));
      continue;
    }

    if (arg.startsWith('--codex-home=')) {
      options.codexHome = expandHomePath(arg.slice('--codex-home='.length));
      continue;
    }

    fail(`unknown argument: ${arg}`);
  }

  return options;
}

function fail(message) {
  console.error(message);
  process.exit(1);
}

function parseDailyBudgetPercent(value) {
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    fail(`invalid --daily-budget-percent value: ${value}`);
  }
  return parsed;
}

function parseDailyCutoffHour(value) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed) || parsed < 0 || parsed > 23) {
    fail(`invalid --daily-cutoff-hour value: ${value}`);
  }
  return parsed;
}

function resolveStateDbPath(codexHome) {
  const root = path.resolve(codexHome);
  const preferred = ['state_5.sqlite', 'state.sqlite'].map((name) => path.join(root, name));
  const dynamicCandidates = [];

  if (fs.existsSync(root) && fs.statSync(root).isDirectory()) {
    for (const entry of fs.readdirSync(root)) {
      if (/^state(?:_\d+)?\.sqlite$/.test(entry)) {
        dynamicCandidates.push(path.join(root, entry));
      }
    }
  }

  const allCandidates = [...preferred, ...dynamicCandidates];
  const uniqueCandidates = [...new Set(allCandidates)].filter((candidate) => fs.existsSync(candidate));
  uniqueCandidates.sort((left, right) => {
    const leftStat = fs.statSync(left);
    const rightStat = fs.statSync(right);
    return rightStat.mtimeMs - leftStat.mtimeMs;
  });

  if (uniqueCandidates.length === 0) {
    fail(`state DB not found in ${abbreviateHome(root)}`);
  }

  return uniqueCandidates[0];
}

function readLastRolloutPath(stateDbPath, source) {
  const safeSource = escapeSqlLiteral(source);

  try {
    return execFileSync(
      'sqlite3',
      [stateDbPath, `select rollout_path from threads where source='${safeSource}' order by created_at desc limit 1;`],
      { encoding: 'utf8' },
    ).trim();
  } catch (error) {
    if (error.code === 'ENOENT') {
      fail('sqlite3 CLI is required but was not found on PATH');
    }
    fail(`failed to query ${abbreviateHome(stateDbPath)}: ${error.message}`);
  }
}

function readLastRateLimits(rolloutPath) {
  if (!rolloutPath) {
    fail('no rollout found for the requested source');
  }

  if (!fs.existsSync(rolloutPath)) {
    fail(`rollout file not found: ${abbreviateHome(rolloutPath)}`);
  }

  const lines = fs.readFileSync(rolloutPath, 'utf8').split('\n').filter(Boolean);
  let rateLimits = null;

  for (const line of lines) {
    let entry;
    try {
      entry = JSON.parse(line);
    } catch {
      continue;
    }

    if (entry.type === 'event_msg' && entry.payload?.type === 'token_count' && entry.payload.rate_limits) {
      rateLimits = entry.payload.rate_limits;
    }
  }

  if (!rateLimits) {
    fail(`no rate_limits token_count event found in ${abbreviateHome(rolloutPath)}`);
  }

  return rateLimits;
}

function countFutureDailyCutoffs(now, resetAt, cutoffHour) {
  if (resetAt <= now) {
    return 0;
  }

  const nextCutoff = new Date(now);
  nextCutoff.setHours(cutoffHour, 0, 0, 0);

  if (now.getTime() >= nextCutoff.getTime()) {
    nextCutoff.setDate(nextCutoff.getDate() + 1);
  }

  let count = 0;
  while (nextCutoff.getTime() <= resetAt.getTime()) {
    count += 1;
    nextCutoff.setDate(nextCutoff.getDate() + 1);
  }

  return count;
}

function formatLocalDate(date) {
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZoneName: 'short',
  }).format(date);
}

function formatPercent(value) {
  const rounded = roundPercent(value);
  return Number.isInteger(rounded) ? `${rounded}` : `${rounded.toFixed(1)}`;
}

function roundPercent(value) {
  return Math.round(value * 10) / 10;
}

function buildStatus(options) {
  const codexHome = path.resolve(options.codexHome || process.env.CODEX_HOME || path.join(os.homedir(), '.codex'));
  const stateDbPath = resolveStateDbPath(codexHome);
  const rolloutPath = readLastRolloutPath(stateDbPath, options.source);
  const rateLimits = readLastRateLimits(rolloutPath);

  const now = new Date();
  const primaryResetAt = new Date(rateLimits.primary.resets_at * 1000);
  const secondaryResetAt = new Date(rateLimits.secondary.resets_at * 1000);
  const primaryRemainingPercent = roundPercent(Math.max(0, 100 - rateLimits.primary.used_percent));
  const secondaryRemainingPercent = roundPercent(Math.max(0, 100 - rateLimits.secondary.used_percent));
  const daysLeft = countFutureDailyCutoffs(now, secondaryResetAt, options.dailyCutoffHour);
  const rawDailyLeftExtra = secondaryRemainingPercent - daysLeft * options.dailyBudgetPercent;
  const dailyLeftExtraPercent = roundPercent(Math.max(0, rawDailyLeftExtra));

  const status = {
    source: options.source,
    checked_at: Math.floor(now.getTime() / 1000),
    checked_at_local: formatLocalDate(now),
    limit_id: rateLimits.limit_id ?? null,
    limit_name: rateLimits.limit_name ?? null,
    plan_type: rateLimits.plan_type ?? null,
    primary: {
      used_percent: rateLimits.primary.used_percent,
      remaining_percent: primaryRemainingPercent,
      resets_at: rateLimits.primary.resets_at,
      resets_at_local: formatLocalDate(primaryResetAt),
      window_duration_mins: rateLimits.primary.window_minutes ?? null,
    },
    secondary: {
      used_percent: rateLimits.secondary.used_percent,
      remaining_percent: secondaryRemainingPercent,
      resets_at: rateLimits.secondary.resets_at,
      resets_at_local: formatLocalDate(secondaryResetAt),
      window_duration_mins: rateLimits.secondary.window_minutes ?? null,
      days_left_at_daily_cutoff: daysLeft,
      daily_budget_percent: options.dailyBudgetPercent,
      daily_cutoff_hour: options.dailyCutoffHour,
      daily_left_extra_percent: dailyLeftExtraPercent,
      daily_left_extra_raw_percent: roundPercent(rawDailyLeftExtra),
    },
  };

  if (options.showPaths) {
    status.paths = {
      codex_home: abbreviateHome(codexHome),
      state_db: abbreviateHome(stateDbPath),
      rollout_path: abbreviateHome(rolloutPath),
    };
  }

  return status;
}

function printHuman(status) {
  const formulaLeft = formatPercent(status.secondary.remaining_percent);
  const daysLeft = status.secondary.days_left_at_daily_cutoff;
  const formulaResult = formatPercent(status.secondary.daily_left_extra_percent);
  const cutoffHour = status.secondary.daily_cutoff_hour;

  console.log(`source: ${status.source}`);
  console.log(`limit bucket: ${status.limit_id ?? 'unknown'}${status.limit_name ? ` (${status.limit_name})` : ''}`);
  console.log(`plan: ${status.plan_type ?? 'unknown'}`);
  console.log(`checked: ${status.checked_at_local}`);
  console.log(`primary: ${formatPercent(status.primary.used_percent)}% used, ${status.primary.window_duration_mins ?? '?'} min window, reset ${status.primary.resets_at_local}`);
  console.log(`secondary: ${formatPercent(status.secondary.used_percent)}% used, ${formatPercent(status.secondary.remaining_percent)}% left, ${status.secondary.window_duration_mins ?? '?'} min window, reset ${status.secondary.resets_at_local}`);
  console.log(`days_left_until_${cutoffHour}h_cutoff: ${daysLeft}`);
  console.log(`formula: ${formulaLeft} - ${daysLeft} * ${status.secondary.daily_budget_percent} = ${formulaResult}`);
  console.log(`daily_left_extra: ${formulaResult}%`);
}

const options = parseArgs(process.argv.slice(2));
const status = buildStatus(options);

if (options.json) {
  console.log(JSON.stringify(status, null, 2));
} else {
  printHuman(status);
}
