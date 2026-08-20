import 'package:flutter/material.dart';

/// Mirrors the color palette used by the web dashboard
/// (assets/style.css) so the mobile app feels like the same product.
class AppColors {
  static const bg = Color(0xFF111827);
  static const card = Color(0xFF1F2937);
  static const border = Color(0xFF374151);
  static const accent = Color(0xFF38BDF8);
  static const good = Color(0xFF22C55E);
  static const suspect = Color(0xFFEAB308);
  static const bad = Color(0xFFEF4444);
  static const textMuted = Color(0xFF9CA3AF);
  static const textPrimary = Color(0xFFF3F4F6);
}

ThemeData buildAppTheme() {
  final base = ThemeData(
    brightness: Brightness.dark,
    useMaterial3: true,
    scaffoldBackgroundColor: AppColors.bg,
    colorScheme: const ColorScheme.dark(
      primary: AppColors.accent,
      surface: AppColors.card,
      error: AppColors.bad,
    ),
  );

  return base.copyWith(
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.bg,
      foregroundColor: AppColors.textPrimary,
      elevation: 0,
    ),
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: AppColors.card,
      selectedItemColor: AppColors.accent,
      unselectedItemColor: AppColors.textMuted,
    ),
    dataTableTheme: const DataTableThemeData(
      headingTextStyle: TextStyle(color: AppColors.textMuted, fontWeight: FontWeight.bold),
      dataTextStyle: TextStyle(color: AppColors.textPrimary),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.accent,
        foregroundColor: AppColors.bg,
        padding: const EdgeInsets.symmetric(vertical: 14),
        textStyle: const TextStyle(fontWeight: FontWeight.bold),
      ),
    ),
    inputDecorationTheme: const InputDecorationTheme(
      labelStyle: TextStyle(color: AppColors.textMuted),
      enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: AppColors.border)),
      focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: AppColors.accent)),
    ),
    textTheme: base.textTheme.apply(
      bodyColor: AppColors.textPrimary,
      displayColor: AppColors.textPrimary,
    ),
  );
}
