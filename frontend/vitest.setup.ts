import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// unmount what each test rendered (auto-cleanup needs vitest globals, which we keep off)
afterEach(() => cleanup());
