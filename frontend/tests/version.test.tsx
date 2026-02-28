/**
 * Tests for issue #26 — version string feature.
 * Covers: useAppVersion hook, SettingsPage System section,
 * Layout version badge (render + copy-to-clipboard flash).
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { renderHook } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { useAppVersion } from '../src/hooks/useAppVersion'
import { SettingsPage } from '../src/pages/SettingsPage'
import { Layout } from '../src/components/Layout'
import type { HealthResponse } from '../src/types/api'

// jsdom does not implement window.matchMedia — stub it globally for this file
beforeAll(() => {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
})

// ── helpers ────────────────────────────────────────────────────────────────────

function mockHealthFetch(data: HealthResponse, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve(data),
  })
}

function mockAllFetch(healthData: HealthResponse) {
  // Layout also triggers scans/devices/risks fetches via hooks in child pages;
  // route the /health call to the real mock and everything else to empty arrays.
  return vi.fn().mockImplementation((url: string) => {
    if (url === '/health') {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(healthData) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  })
}

beforeEach(() => vi.restoreAllMocks())
afterEach(() => vi.restoreAllMocks())

// ── useAppVersion ──────────────────────────────────────────────────────────────

describe('useAppVersion', () => {
  it('returns version from /health on success', async () => {
    vi.stubGlobal('fetch', mockHealthFetch({ status: 'ok', version: '1.2.3' }))
    const { result } = renderHook(() => useAppVersion())
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.version).toBe('1.2.3')
  })

  it('returns null on HTTP error', async () => {
    vi.stubGlobal('fetch', mockHealthFetch({ status: 'error', version: '' }, false))
    const { result } = renderHook(() => useAppVersion())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.version).toBeNull()
  })

  it('returns null on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')))
    const { result } = renderHook(() => useAppVersion())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.version).toBeNull()
  })

  it('fetches /health exactly once on mount', async () => {
    const fetchMock = mockHealthFetch({ status: 'ok', version: '0.1.0' })
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useAppVersion())
    await waitFor(() => expect(result.current.loading).toBe(false))
    const healthCalls = fetchMock.mock.calls.filter((c: string[]) => c[0] === '/health')
    expect(healthCalls).toHaveLength(1)
  })
})

// ── SettingsPage ───────────────────────────────────────────────────────────────

describe('SettingsPage', () => {
  it('renders the System section heading', async () => {
    vi.stubGlobal('fetch', mockHealthFetch({ status: 'ok', version: '0.1.0' }))
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    )
    expect(screen.getByText(/system/i)).toBeTruthy()
  })

  it('shows version number once loaded', async () => {
    vi.stubGlobal('fetch', mockHealthFetch({ status: 'ok', version: '0.1.0' }))
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('v0.1.0')).toBeTruthy())
  })

  it('shows version copy button and flashes ✓ on click', async () => {
    vi.stubGlobal('fetch', mockHealthFetch({ status: 'ok', version: '0.1.0' }))
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('v0.1.0')).toBeTruthy())

    fireEvent.click(screen.getByText('v0.1.0'))
    expect(writeText).toHaveBeenCalledWith('v0.1.0')

    await waitFor(() => expect(screen.getByText('✓ v0.1.0')).toBeTruthy())
  })

  it('shows a dash when version is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('—')).toBeTruthy())
  })
})

// ── Layout version badge ───────────────────────────────────────────────────────

describe('Layout version badge', () => {
  it('renders version string in header', async () => {
    vi.stubGlobal('fetch', mockAllFetch({ status: 'ok', version: '0.1.0' }))
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('v0.1.0')).toBeTruthy())
  })

  it('flashes ✓ after clicking the version badge', async () => {
    vi.stubGlobal('fetch', mockAllFetch({ status: 'ok', version: '0.1.0' }))
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })

    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('v0.1.0')).toBeTruthy())
    fireEvent.click(screen.getByText('v0.1.0'))
    expect(writeText).toHaveBeenCalledWith('v0.1.0')
    await waitFor(() => expect(screen.getByText('✓')).toBeTruthy())
  })

  it('does not render a version badge while loading', () => {
    // Never resolves — simulates in-flight state
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise(() => {})))
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>,
    )
    // v0.x.x pattern should not appear in the header while loading
    expect(screen.queryByText(/^v\d/)).toBeNull()
  })
})
