#!/usr/bin/env bash
set -eu

RELEASE_REPO="pdomain/pdomain-ops"

. "$(dirname "$0")/release-common.sh"
pdomain_release_main "$@"
