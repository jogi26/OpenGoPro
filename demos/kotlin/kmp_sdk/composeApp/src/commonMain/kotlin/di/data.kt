/* data.kt/Open GoPro, Version 2.0 (C) Copyright 2021 GoPro, Inc. (http://gopro.com/OpenGoPro). */
/* This copyright was auto-generated on Tue Feb 18 18:41:27 UTC 2025 */

package di

import data.IAppPreferences
import data.IAppPreferencesImpl
import org.koin.dsl.module

val dataModule = module { single<IAppPreferences> { IAppPreferencesImpl(get()) } }
