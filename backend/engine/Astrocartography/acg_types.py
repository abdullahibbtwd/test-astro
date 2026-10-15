#!/usr/bin/env python3
"""acg_types.py — in-process typing of the ACG artifacts (acg.json, locate.json,
city_scan.json). The language-agnostic twin of acg.json is acg_schema.json."""

from __future__ import annotations

from typing import Literal, Optional, TypedDict

Angle = Literal["MC", "IC", "ASC", "DSC"]
Tier = Literal["tight", "strong", "wide"]
Status = Literal["ok", "absent"]
Vertex = list[float]                      # [lon, lat]


class Absence(TypedDict):
    reason: str
    detail: Optional[str]


class Joins(TypedDict):
    MC_at_lat: Optional[float]
    IC_at_lat: Optional[float]


class MeridianLine(TypedDict):
    vertices: list[Vertex]


class HorizonLine(TypedDict):
    vertices: list[Vertex]
    joins: Joins


class Lines(TypedDict):
    MC: MeridianLine
    IC: MeridianLine
    ASC: HorizonLine
    DSC: HorizonLine


class Equatorial(TypedDict):
    ra: float
    dec: float
    dist: float


class BodyLines(TypedDict):
    body: str
    read_in_v1: bool
    out_of_scope: Optional[str]
    equatorial: Equatorial
    circumpolar_lat_limit: float
    lines: Lines


class ACG(TypedDict):
    schema_version: str
    meta: dict
    status: Status
    absence: Optional[Absence]
    bodies: list[BodyLines]


class Place(TypedDict):
    query: Optional[str]
    name: str
    name_tr: str
    lat: float
    lon: float
    country_code: Optional[str]
    source: Literal["gazetteer", "geocoder", "manual"]


class LineNear(TypedDict):
    body: str
    angle: Angle
    distance_km: float
    tier: Tier
    read_in_v1: bool
    nearest_point: Vertex
    side: Literal["east", "west"]


class HouseShift(TypedDict):
    body: str
    natal_house: int
    relocated_house: int
    angular_after: bool


class Relocation(TypedDict, total=False):
    status: Status
    absence: Optional[Absence]
    chart_path: Optional[str]
    relocated_from: dict


class Locate(TypedDict):
    schema_version: str
    place: Optional[Place]
    status: Status
    absence: Optional[Absence]
    lines_near: list[LineNear]
    relocation: Relocation
    house_diff: list[HouseShift]
