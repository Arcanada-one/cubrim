// Copyright 2026 The Cubrim Authors (demo fork, CUBR-0079).
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef NET_FILTER_CBM_SOURCE_STREAM_H_
#define NET_FILTER_CBM_SOURCE_STREAM_H_

#include <stddef.h>

#include <memory>

#include "net/base/net_export.h"
#include "net/filter/filter_source_stream.h"

namespace net {

// Applies `cbm` (Cubrim Web Profile) content decoding to a response stream.
// Demo fork only — the coding is unregistered and gated behind
// net::features::kCbmContentEncoding.
NET_EXPORT_PRIVATE std::unique_ptr<FilterSourceStream> CreateCbmSourceStream(
    std::unique_ptr<SourceStream> upstream);

// Test-only controls for proving request-local aggregate admission and
// release. Production callers must use the fixed 512 MiB policy.
NET_EXPORT_PRIVATE size_t CbmAggregateMemoryBudgetForTesting();
NET_EXPORT_PRIVATE void SetCbmAggregateMemoryBudgetForTesting(size_t bytes);

}  // namespace net

#endif  // NET_FILTER_CBM_SOURCE_STREAM_H_
