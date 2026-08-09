from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SustainabilityAssessment:
    waste_score: int
    travel_score: int
    sourcing_score: int

    @property
    def total(self) -> int:
        return self.waste_score + self.travel_score + self.sourcing_score
