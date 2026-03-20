document.addEventListener("DOMContentLoaded", function () {
  const configElement = document.getElementById("sentify-config");
  if (!configElement) return;

  const {
    recommendationInputs = [],
    maxNewsLookbackDays = 0,
    startDay = 0,
    endDay = 2,
  } = JSON.parse(configElement.textContent);

  const slider = document.getElementById("slider");
  if (!slider) return;

  const formatter = {
    to: (value) =>
      `${parseInt(value, 10)} day${parseInt(value, 10) !== 1 ? "s" : ""}`,
    from: (value) =>
      parseInt(String(value).replace(" day", "").replace("s", ""), 10),
  };

  const lo = Math.max(0, Math.min(startDay, endDay, maxNewsLookbackDays));
  const hi = Math.max(
    lo,
    Math.min(Math.max(startDay, endDay), maxNewsLookbackDays),
  );

  noUiSlider.create(slider, {
    connect: true,
    range: { min: 0, max: maxNewsLookbackDays },
    step: 1,
    start: [lo, hi],
    tooltips: [formatter, formatter],
  });

  const form = document.querySelector(".search-form");
  const hiddenStart = document.getElementById("start");
  const hiddenEnd = document.getElementById("end");

  slider.noUiSlider.on("update", (values) => {
    hiddenStart.value = parseInt(values[0], 10);
    hiddenEnd.value = parseInt(values[1], 10);
  });

  const [v0, v1] = slider.noUiSlider.get();
  hiddenStart.value = parseInt(v0, 10);
  hiddenEnd.value = parseInt(v1, 10);

  const tuningInputs = document.querySelectorAll("[data-value-target]");

  const formatTuningValue = (input) => {
    const value = parseFloat(input.value);
    switch (input.dataset.format) {
      case "hours":
        if (value === 0) return "0 h";
        if (value % 24 === 0) return `${value / 24} d`;
        return `${value} h`;
      case "percent":
        return `${Math.round(value * 100)}%`;
      case "words":
        return `${Math.round(value)} words`;
      default:
        return value.toFixed(2);
    }
  };

  const syncTuningValue = (input) => {
    const target = document.getElementById(input.dataset.valueTarget);
    if (target) target.textContent = formatTuningValue(input);
  };

  const getWeightConfig = () => ({
    recency_half_life_hours: parseFloat(
      document.getElementById("recency_half_life_hours").value,
    ),
    recency_floor: parseFloat(document.getElementById("recency_floor").value),
    content_length_target_words: parseInt(
      document.getElementById("content_length_target_words").value,
      10,
    ),
    content_length_min: parseFloat(
      document.getElementById("content_length_min").value,
    ),
    content_length_max: parseFloat(
      document.getElementById("content_length_max").value,
    ),
  });

  const normalizeRecommendationScore = (action, score) => {
    if (action === "Positive") return score / 2 + 0.5;
    return (1 - score) / 2;
  };

  const getRecencyWeight = (ageSeconds, weightConfig) => {
    if (ageSeconds === null || ageSeconds === undefined) return 1.0;
    if (weightConfig.recency_half_life_hours <= 0) return 1.0;

    const normalizedAgeSeconds = Math.max(Number(ageSeconds), 0);
    const halfLifeSeconds = weightConfig.recency_half_life_hours * 3600;
    const decay = Math.pow(0.5, normalizedAgeSeconds / halfLifeSeconds);
    return (
      weightConfig.recency_floor + (1 - weightConfig.recency_floor) * decay
    );
  };

  const getContentLengthWeight = (contentLengthWords, weightConfig) => {
    if (contentLengthWords === null || contentLengthWords === undefined) {
      return 1.0;
    }
    if (weightConfig.content_length_target_words <= 0) return 1.0;

    const normalizedContentLength = Math.max(Number(contentLengthWords), 0);
    const progress = Math.min(
      normalizedContentLength / weightConfig.content_length_target_words,
      1.0,
    );
    return (
      weightConfig.content_length_min +
      (weightConfig.content_length_max - weightConfig.content_length_min) *
        progress
    );
  };

  const getArticleWeight = (item, weightConfig) =>
    getRecencyWeight(item.age_seconds, weightConfig) *
    getContentLengthWeight(item.content_length_words, weightConfig);

  const getRecommendedAction = (items, weightConfig) => {
    let totalWeight = 0.0;
    let action = "";
    let actionColumnScore = 0.0;
    let correspondColumnScore = 0.0;
    let positiveWeight = 0.0;
    let negativeWeight = 0.0;

    items.forEach((item) => {
      if (item.label === "Neutral") return;

      const articleWeight = getArticleWeight(item, weightConfig);
      totalWeight += articleWeight;
      if (item.label === "Positive") positiveWeight += articleWeight;
      if (item.label === "Negative") negativeWeight += articleWeight;
    });

    action = positiveWeight >= negativeWeight ? "Positive" : "Negative";

    items.forEach((item) => {
      if (item.label === "Neutral") return;

      const articleWeight = getArticleWeight(item, weightConfig);
      if (item.label === "Positive") {
        if (action === "Positive") {
          actionColumnScore += articleWeight * item.highest_score;
          correspondColumnScore -= articleWeight * item.corresponding_score;
        } else {
          actionColumnScore -= articleWeight * item.highest_score;
          correspondColumnScore += articleWeight * item.corresponding_score;
        }
      }

      if (item.label === "Negative") {
        if (action === "Negative") {
          actionColumnScore += articleWeight * item.highest_score;
          correspondColumnScore -= articleWeight * item.corresponding_score;
        } else {
          actionColumnScore -= articleWeight * item.highest_score;
          correspondColumnScore += articleWeight * item.corresponding_score;
        }
      }
    });

    if (action === "Positive") {
      correspondColumnScore = -correspondColumnScore;
    } else {
      actionColumnScore = -actionColumnScore;
    }

    if (totalWeight) {
      actionColumnScore /= totalWeight;
      correspondColumnScore /= totalWeight;
    }

    if (
      actionColumnScore - correspondColumnScore >= 0 &&
      actionColumnScore - correspondColumnScore <= 0.2
    ) {
      return { recommendation: "Hold", confidence: 0.0 };
    }

    if (actionColumnScore > correspondColumnScore) {
      return {
        recommendation: "Buy",
        confidence: normalizeRecommendationScore(action, actionColumnScore),
      };
    }

    return {
      recommendation: "Sell",
      confidence: normalizeRecommendationScore(action, correspondColumnScore),
    };
  };

  const updateRecommendationCard = () => {
    const actionElements = document.querySelectorAll(
      "[data-recommendation-action]",
    );
    const confidenceElements = document.querySelectorAll(
      "[data-confidence-index]",
    );
    if (
      actionElements.length === 0 ||
      confidenceElements.length === 0 ||
      recommendationInputs.length === 0
    ) {
      return;
    }

    const result = getRecommendedAction(
      recommendationInputs,
      getWeightConfig(),
    );
    actionElements.forEach((actionElement) => {
      actionElement.textContent = result.recommendation;
      actionElement.classList.remove(
        "recommendation-buy",
        "recommendation-hold",
        "recommendation-sell",
      );
      actionElement.classList.add(
        result.recommendation === "Buy"
          ? "recommendation-buy"
          : result.recommendation === "Hold"
            ? "recommendation-hold"
            : "recommendation-sell",
      );
    });

    confidenceElements.forEach((confidenceElement) => {
      if (result.recommendation === "Hold") {
        confidenceElement.style.display = "none";
        return;
      }

      confidenceElement.style.display = "block";
      confidenceElement.innerHTML = `<i class="fas fa-chart-line me-2"></i>Confidence: ${result.confidence.toFixed(3)}`;
    });
  };

  tuningInputs.forEach((input) => {
    syncTuningValue(input);
    input.addEventListener("input", function () {
      const minWeight = document.getElementById("content_length_min");
      const maxWeight = document.getElementById("content_length_max");

      if (
        input.id === "content_length_min" &&
        parseFloat(input.value) > parseFloat(maxWeight.value)
      ) {
        maxWeight.value = input.value;
        syncTuningValue(maxWeight);
      }

      if (
        input.id === "content_length_max" &&
        parseFloat(input.value) < parseFloat(minWeight.value)
      ) {
        minWeight.value = input.value;
        syncTuningValue(minWeight);
      }

      syncTuningValue(input);
      updateRecommendationCard();
    });
  });

  updateRecommendationCard();

  if (form) {
    form.addEventListener("submit", function () {
      const loading = document.getElementById("loading");
      if (loading) loading.style.display = "block";
    });
  }
});
