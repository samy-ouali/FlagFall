using System.Collections.Generic;
using System.IO;
using UnityEngine;

// =========================================================
// FlagModel : donnees produites par le pipeline ML (ml/train_difficulty.py)
// et lues par le jeu au demarrage.
// Fichier : Assets/StreamingAssets/flag_model.json
// =========================================================
[System.Serializable]
public class FlagModelEntry
{
    public string code;          // "fr", "de"... = nom du fichier image du drapeau
    public string name_fr;
    public string name_en;
    public float difficulty;     // > 0 : plus difficile que la moyenne
    public string[] similar;     // drapeaux qui se ressemblent (CLIP + confusions observees)
}

[System.Serializable]
public class FlagModel
{
    public string source;        // "playtests", "simulated" ou "similarity only"
    public string created;
    public int n_events;
    public float target_success = 0.7f;
    public FlagModelEntry[] countries;

    public const string FileName = "flag_model.json";

    // Retourne null si le fichier n'existe pas (le jeu repasse alors en mode aleatoire).
    public static FlagModel Load()
    {
        string path = Path.Combine(Application.streamingAssetsPath, FileName);
        if (!File.Exists(path))
        {
            Debug.LogWarning("FlagModel : fichier introuvable " + path);
            return null;
        }
        return JsonUtility.FromJson<FlagModel>(File.ReadAllText(path));
    }

    public Dictionary<string, FlagModelEntry> ByCode()
    {
        var dict = new Dictionary<string, FlagModelEntry>();
        if (countries != null)
            foreach (var c in countries) dict[c.code] = c;
        return dict;
    }
}
