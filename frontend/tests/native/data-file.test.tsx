import { shareAccountData } from "../../src/features/exports/data-file";
import * as Sharing from "expo-sharing";
const mockWrite = jest.fn();
const mockDelete = jest.fn();
jest.mock("expo-file-system", () => ({
  Paths: { cache: "cache" },
  File: class {
    uri = "file:///cache/export.json";
    exists = true;
    write = mockWrite;
    delete = mockDelete;
  },
}));
jest.mock("expo-sharing", () => ({
  isAvailableAsync: jest.fn(),
  shareAsync: jest.fn(),
}));
beforeEach(() => {
  jest.clearAllMocks();
  (Sharing.isAvailableAsync as jest.Mock).mockResolvedValue(true);
  (Sharing.shareAsync as jest.Mock).mockResolvedValue(undefined);
});
test("account data reaches native sharing and temporary copy is removed", async () => {
  const data = {
    format: "astrology-local-export-v1",
    profiles: [{ label: "Test" }],
  };
  await shareAccountData(data);
  expect(JSON.parse(mockWrite.mock.calls[0][0])).toEqual(data);
  expect(Sharing.shareAsync).toHaveBeenCalledWith("file:///cache/export.json", {
    mimeType: "application/json",
    UTI: "public.json",
  });
  expect(mockDelete).toHaveBeenCalledTimes(1);
});
test("sharing failure cleans the temporary copy and reaches the error UI", async () => {
  (Sharing.shareAsync as jest.Mock).mockRejectedValue(
    new Error("Share failed"),
  );
  await expect(
    shareAccountData({ format: "astrology-local-export-v1" }),
  ).rejects.toThrow("Share failed");
  expect(mockDelete).toHaveBeenCalledTimes(1);
});
test("unavailable sharing and invalid exports never write private data", async () => {
  await expect(shareAccountData({ status: "queued" })).rejects.toThrow(
    "Invalid account export",
  );
  (Sharing.isAvailableAsync as jest.Mock).mockResolvedValue(false);
  await expect(
    shareAccountData({ format: "astrology-local-export-v1" }),
  ).rejects.toThrow("File sharing unavailable");
  expect(mockWrite).not.toHaveBeenCalled();
});
