"""Structured LLM output and local source checks."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Claim(Record):
    text: str
    profile_quotes: list[str]


class JobDetail(Record):
    text: str
    job_quote: str


class Entry(Record):
    heading: Claim | None
    details: list[Claim]
    bullets: list[Claim]


class Section(Record):
    heading: str
    entries: list[Entry]


class Requirement(Record):
    requirement: str
    priority: Literal["required", "preferred", "unspecified"]
    status: Literal["supported", "partial", "missing"]
    profile_quotes: list[str]
    note: str


class GeneratedCV(Record):
    candidate_name: Claim
    job_title: JobDetail | None
    company: JobDetail | None
    language: str
    contacts: list[Claim]
    sections: list[Section]
    requirements: list[Requirement]
    wording_changes: list[str]
    warnings: list[str]
    clarification_questions: list[str]
    max_pages: int | None = Field(description="Template page limit; null for unrestricted academic CVs.")

    def claims(self):
        yield self.candidate_name
        yield from self.contacts
        for section in self.sections:
            for entry in section.entries:
                if entry.heading:
                    yield entry.heading
                yield from entry.details
                yield from entry.bullets

    def validate_sources(self, profile: str, job: str) -> None:
        if self.clarification_questions:
            raise ValueError("The model requires clarification; review the saved report before retrying.")
        if not self.candidate_name.text.strip() or not self.sections:
            raise ValueError("The response is missing the candidate name or CV sections.")
        if self.candidate_name.text not in profile:
            raise ValueError("The candidate name must appear verbatim in the profile.")
        for claim in self.claims():
            if not claim.text.strip() or not claim.profile_quotes:
                raise ValueError("A CV claim has no text or source evidence.")
            if any(not quote.strip() or quote not in profile for quote in claim.profile_quotes):
                raise ValueError("A CV claim cites evidence absent from the profile.")
        for detail in (self.job_title, self.company):
            if detail and (not detail.text.strip() or not detail.job_quote.strip()
                           or detail.job_quote not in job or detail.text not in detail.job_quote):
                raise ValueError("Job metadata must appear verbatim in its advertisement quotation.")
        for requirement in self.requirements:
            if any(not quote.strip() or quote not in profile for quote in requirement.profile_quotes):
                raise ValueError("A requirement cites evidence absent from the profile.")
            if requirement.status in ("supported", "partial") and not requirement.profile_quotes:
                raise ValueError("A supported requirement has no source evidence.")
        if self.max_pages is not None and self.max_pages < 1:
            raise ValueError("The template page limit must be positive.")
