import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { WelcomePageComponent } from './modules/welcome-page/welcome-page.component';
import { HomeComponent } from './modules/home/home.component';

const routes: Routes = [
  { path: '', redirectTo: 'welcome', pathMatch: 'full' }, // default route goes to welcome
  { path: 'welcome', component: WelcomePageComponent },
  { path: 'login', loadChildren: () => import('@modules/login/login.module').then(m => m.LoginModule) },
  { path: '', loadChildren: () => import('./modules/home/home.module').then(m => m.HomeModule) }
  // { path: '**', redirectTo: 'welcome' } // fallback
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule {}
