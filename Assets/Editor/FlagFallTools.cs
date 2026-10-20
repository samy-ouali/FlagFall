using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

// =========================================================
// FlagFallTools : menu "FlagFall" dans la barre de Unity.
//
// 1. "Setup flags and country list" : regle l'import des nouveaux drapeaux
//    (memes reglages que les 15 drapeaux d'origine) et remplit automatiquement
//    la liste "countries" du GameManager a partir de flag_model.json.
// 2. "Open logs folder" : ouvre le dossier ou le jeu enregistre les parties.
// 3. "Copy logs to ml/data/logs" : copie ces fichiers dans le projet pour l'entrainement.
// =========================================================
public static class FlagFallTools
{
    const string FlagsFolder = "Assets/Flags";
    const float PixelsPerUnit = 1000f;   // reglage des drapeaux d'origine

    [MenuItem("FlagFall/Setup flags and country list")]
    public static void SetupFlagsAndCountries()
    {
        FlagModel model = FlagModel.Load();
        if (model == null || model.countries == null)
        {
            EditorUtility.DisplayDialog("FlagFall", "flag_model.json introuvable dans Assets/StreamingAssets.", "OK");
            return;
        }

        // 1. Reglages d'import des drapeaux ajoutes (les drapeaux d'origine ne sont pas modifies).
        int fixedCount = 0;
        foreach (var entry in model.countries)
        {
            string path = FlagsFolder + "/" + entry.code + ".png";
            var importer = AssetImporter.GetAtPath(path) as TextureImporter;
            if (importer == null) continue;
            bool alreadyOk = importer.textureType == TextureImporterType.Sprite
                             && Mathf.Approximately(importer.spritePixelsPerUnit, PixelsPerUnit);
            if (alreadyOk) continue;
            importer.textureType = TextureImporterType.Sprite;
            importer.spriteImportMode = SpriteImportMode.Single;
            importer.spritePixelsPerUnit = PixelsPerUnit;
            importer.alphaIsTransparency = true;
            importer.maxTextureSize = 2048;
            importer.SaveAndReimport();
            fixedCount++;
        }

        // 2. Liste des pays du GameManager de la scene ouverte.
        var gm = Object.FindFirstObjectByType<GameManager>();
        if (gm == null)
        {
            EditorUtility.DisplayDialog("FlagFall", "Aucun GameManager dans la scene ouverte.", "OK");
            return;
        }
        Undo.RecordObject(gm, "Fill FlagFall countries");
        var list = new List<Country>();
        var missing = new List<string>();
        foreach (var entry in model.countries)
        {
            string path = FlagsFolder + "/" + entry.code + ".png";
            Sprite sprite = AssetDatabase.LoadAllAssetsAtPath(path).OfType<Sprite>().FirstOrDefault();
            if (sprite == null) { missing.Add(entry.code); continue; }
            list.Add(new Country { countryName = entry.name_fr, flag = sprite });
        }
        gm.countries = list;
        EditorUtility.SetDirty(gm);
        EditorSceneManager.MarkSceneDirty(gm.gameObject.scene);

        string msg = list.Count + " pays dans le GameManager (" + fixedCount + " drapeaux re-importes).";
        if (missing.Count > 0) msg += "\nImages manquantes : " + string.Join(", ", missing);
        msg += "\n\nPense a sauvegarder la scene (Cmd+S).";
        EditorUtility.DisplayDialog("FlagFall", msg, "OK");
    }

    [MenuItem("FlagFall/Open logs folder")]
    public static void OpenLogsFolder()
    {
        Directory.CreateDirectory(GameLogger.LogFolder);
        EditorUtility.RevealInFinder(GameLogger.LogFolder);
    }

    [MenuItem("FlagFall/Copy logs into the project (ml > data > logs)")]
    public static void CopyLogs()
    {
        string dest = Path.Combine(Directory.GetParent(Application.dataPath).FullName, "ml", "data", "logs");
        Directory.CreateDirectory(dest);
        int n = 0;
        if (Directory.Exists(GameLogger.LogFolder))
            foreach (var file in Directory.GetFiles(GameLogger.LogFolder, "*.csv"))
            {
                File.Copy(file, Path.Combine(dest, Path.GetFileName(file)), true);
                n++;
            }
        EditorUtility.DisplayDialog("FlagFall", n + " fichier(s) copie(s) dans ml/data/logs.", "OK");
    }
}
