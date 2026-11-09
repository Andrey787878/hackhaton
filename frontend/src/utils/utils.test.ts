import { describe, expect, it } from "vitest";
import { buildUrl, filenameFrom } from "../api/client";
import { errorFromBody, translate } from "../api/errors";
import { formatBytes, fromLocalInput, plural, splitDuration, toLocalInput } from "./format";
import { expertTotal, inRange, weightShare } from "./scoring";
import { computeOffset } from "./serverClock";
import { archiveProblem, passwordProblems, USERNAME } from "./validation";

const criteria = [
  { id: 1, min_score: 0, max_score: 10, weight: "3" },
  { id: 2, min_score: 0, max_score: 5, weight: "1" },
];

describe("expertTotal — формула docs/SCORING.md", () => {
  it("даёт 85.00 для 8/10 и 5/5 с весами 3 и 1, как сервер", () => {
    expect(expertTotal(criteria, { 1: 8, 2: 5 })).toBe(85);
  });
  it("не считает неполную оценку", () => {
    expect(expertTotal(criteria, { 1: 8 })).toBeNull();
  });
  it("учитывает ненулевой минимум", () => {
    expect(expertTotal([{ id: 1, min_score: 1, max_score: 5, weight: 1 }], { 1: 3 })).toBe(50);
  });
  it("проверяет диапазон и долю веса", () => {
    expect(inRange(criteria[0], 10)).toBe(true);
    expect(inRange(criteria[0], 11)).toBe(false);
    expect(inRange(criteria[0], 2.5)).toBe(false);
    expect(weightShare(criteria, criteria[0])).toBe(0.75);
  });
});

describe("обратный отсчёт и даты", () => {
  it("раскладывает длительность", () => {
    expect(splitDuration(((2 * 24 + 3) * 3600 + 4 * 60 + 5) * 1000 + 999)).toMatchObject({
      days: 2,
      hours: 3,
      minutes: 4,
      seconds: 5,
    });
    expect(splitDuration(-5000).totalMs).toBe(0);
  });
  it("datetime-local ↔ ISO UTC без потери минут", () => {
    const iso = "2026-11-08T12:30:00.000Z";
    expect(fromLocalInput(toLocalInput(iso))).toBe(iso);
  });
  it("смещение серверных часов учитывает половину RTT", () => {
    expect(computeOffset(10_500, 9_000, 10_000)).toBe(1_000);
  });
  it("форматирует размеры и склонения", () => {
    expect(formatBytes(512)).toBe("512 Б");
    expect(formatBytes(20 * 1024 * 1024)).toBe("20 МиБ");
    expect(plural(1, "команда", "команды", "команд")).toBe("команда");
    expect(plural(3, "команда", "команды", "команд")).toBe("команды");
    expect(plural(11, "команда", "команды", "команд")).toBe("команд");
  });
});

describe("ошибки FastAPI", () => {
  it("берёт detail-строку", () => {
    expect(errorFromBody(409, { detail: "Дедлайн сдачи прошёл." }).message).toBe("Дедлайн сдачи прошёл.");
  });
  it("разбирает 422 по полям", () => {
    const error = errorFromBody(422, {
      detail: [{ loc: ["body", "password"], msg: "Value error, password должен содержать минимум одну цифру." }],
    });
    expect(error.fields.password).toBe("password должен содержать минимум одну цифру.");
    expect(error.message).toContain("Пароль:");
  });
  it("переводит формат RBAC 403", () => {
    expect(errorFromBody(403, { error: "Access denied. Required permission: create-team" }).message).toBe(
      "Недостаточно прав для операции (create-team).",
    );
  });
  it("переводит типовые сообщения Pydantic", () => {
    expect(translate("Field required")).toBe("обязательное поле");
  });
});

describe("HTTP-клиент", () => {
  it("строит URL с параметрами без пустых значений", () => {
    expect(buildUrl("/teams", { limit: 100, case_id: undefined, unread_only: false })).toBe(
      "/api/v1/teams?limit=100&unread_only=false",
    );
  });
  it("читает имя файла из Content-Disposition", () => {
    expect(filenameFrom("attachment; filename*=UTF-8''%D1%80%D0%B5%D1%88%D0%B5%D0%BD%D0%B8%D0%B5.zip", "x")).toBe(
      "решение.zip",
    );
    expect(filenameFrom(null, "fallback.zip")).toBe("fallback.zip");
  });
});

describe("клиентская валидация", () => {
  it("повторяет правила пароля и логина сервера", () => {
    expect(passwordProblems("Demo-password-123!")).toEqual([]);
    expect(passwordProblems("short")).toContain("минимум 8 символов");
    expect(USERNAME.test("demo-user")).toBe(true);
    expect(USERNAME.test("_bad")).toBe(false);
  });
  it("проверяет архив до загрузки", () => {
    expect(archiveProblem({ name: "solution.tar.gz", size: 10 })).toBeNull();
    expect(archiveProblem({ name: "solution.rar", size: 10 })).toMatch(/zip/);
    expect(archiveProblem({ name: "big.zip", size: 21 * 1024 * 1024 })).toMatch(/20/);
  });
});
