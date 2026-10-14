"use client";

import { useState } from "react";
import { usePredictionSetting } from "@/lib/use-prediction";
import { PREDICTION_HELP, PredictionToggle } from "./PredictionStrip";

/**
 * Settings (signed in): the word prediction switch, kept in the account
 * (user_settings.prediction) so it follows the writer to Word and the
 * website. Its own panel and its own announcement, so it stays apart from
 * the other settings' loading and saving.
 */
export function PredictionSettings() {
  const setting = usePredictionSetting(true);
  const [said, setSaid] = useState("");
  return (
    <section className="panel settings-section" aria-labelledby="prediction-title" data-testid="prediction-settings">
      <h2 id="prediction-title" className="panel-title">
        Word prediction
      </h2>
      <div className="setting-row">
        <PredictionToggle
          setting={{
            ...setting,
            set: (on) => {
              setting.set(on);
              setSaid(on ? "Word prediction is on." : "Word prediction is off.");
            },
          }}
          testId="settings-prediction-switch"
          help={`${PREDICTION_HELP} In Word, the words appear in the Next words panel. Your text is never kept.`}
          showHelp
        />
      </div>
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {said}
      </p>
    </section>
  );
}
